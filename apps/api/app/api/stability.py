from __future__ import annotations

import hashlib
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.integrity_step11 import _require_active_criteria, _raw_rows, _validate_scores
from app.db.session import get_db
from app.engine.stability import analyze_stability
from app.models import AnalyticsRun, Event, User
from app.schemas.stability import StabilityAnalysisRequest
from app.security.auth import current_user
from app.security.authorization import event_manager
from app.services.audit import record_audit
from app.services.webhooks import dispatch_event


router = APIRouter(tags=["JudgeGuard Step 13 — Ranking Stability"])


def _hash_payload(payload: dict) -> str:
    blob = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _latest_run(db: Session, event_id: UUID) -> AnalyticsRun | None:
    return db.scalar(
        select(AnalyticsRun)
        .where(
            AnalyticsRun.event_id == event_id,
            AnalyticsRun.kind == "STABILITY",
        )
        .order_by(AnalyticsRun.created_at.desc())
    )


@router.post("/events/{event_id}/judging/stability/analyze")
def analyze_event_stability(
    event_id: UUID,
    payload: StabilityAnalysisRequest,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    rows = _raw_rows(db, event_id)
    if not rows:
        raise HTTPException(status_code=409, detail="No evaluations available for stability analysis")

    criteria = _require_active_criteria(db, event_id)
    _validate_scores(rows, criteria)
    weights = {criterion_id: data["weight"] for criterion_id, data in criteria.items()}

    try:
        result = analyze_stability(
            rows,
            weights,
            normalization_method=payload.normalization_method,
            min_observations=payload.min_observations,
            clip=payload.clip,
            bootstrap_iterations=payload.bootstrap_iterations,
            seed=payload.seed,
            top_k=payload.top_k,
            pairwise_top_n=payload.pairwise_top_n,
            sensitivity_delta=payload.sensitivity_delta,
            sensitivity_steps=payload.sensitivity_steps,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    input_payload = {
        "rows": rows,
        "criteria": criteria,
        "config": payload.model_dump(mode="json"),
    }
    input_hash = _hash_payload(input_payload)

    run = AnalyticsRun(
        event_id=event_id,
        kind="STABILITY",
        method="frozen_normalization_panel_bootstrap_v1",
        input_hash=input_hash,
        result=result,
        created_by=user.id,
    )
    db.add(run)
    db.flush()

    record_audit(
        db,
        event_id=event_id,
        actor_user_id=user.id,
        action="STABILITY_ANALYSIS_COMPLETED",
        entity_type="analytics_run",
        entity_id=str(run.id),
        payload={
            "input_hash": input_hash,
            "method": run.method,
            "bootstrap_iterations": payload.bootstrap_iterations,
            "seed": payload.seed,
            "winner": result["baseline"].get("winner"),
            "winner_change_count": result["rubric_sensitivity"]["diagnostics"]["winner_change_count"],
        },
    )
    db.commit()
    dispatch_event(
        db,
        event_id,
        "analytics.stability.completed",
        {"run_id": str(run.id), "input_hash": input_hash, "method": run.method},
    )

    return {
        "run_id": str(run.id),
        "method": run.method,
        "created_at": run.created_at,
        "result": result,
    }


@router.get("/events/{event_id}/judging/stability/latest")
def latest_stability(
    event_id: UUID,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    run = _latest_run(db, event_id)
    if run is None:
        return {"run": None}
    return {
        "run": {
            "id": str(run.id),
            "created_at": run.created_at,
            "method": run.method,
            "input_hash": run.input_hash,
            "result": run.result,
        }
    }


@router.get("/events/{event_id}/judging/stability/ranking")
def latest_stability_ranking(
    event_id: UUID,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    run = _latest_run(db, event_id)
    if run is None:
        return {"run_id": None, "ranking": None, "rank1_frequency": None}
    result = run.result
    return {
        "run_id": str(run.id),
        "ranking": result.get("baseline", {}).get("ranking", []),
        "rank1_frequency": result.get("bootstrap", {}).get("rank1_frequency", {}),
        "coverage_frequency": result.get("bootstrap", {}).get("coverage_frequency", {}),
        "mean_rank": result.get("bootstrap", {}).get("mean_rank", {}),
        "rank_std_dev": result.get("bootstrap", {}).get("rank_std_dev", {}),
        "top_k": result.get("bootstrap", {}).get("top_k"),
        "top_k_frequency": result.get("bootstrap", {}).get("top_k_frequency", {}),
    }


@router.get("/events/{event_id}/judging/stability/rubric-sensitivity")
def latest_rubric_sensitivity(
    event_id: UUID,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    run = _latest_run(db, event_id)
    if run is None:
        return {"run_id": None, "rubric_sensitivity": None}
    return {
        "run_id": str(run.id),
        "rubric_sensitivity": run.result.get("rubric_sensitivity", {}),
    }
