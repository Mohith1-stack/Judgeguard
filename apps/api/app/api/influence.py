from __future__ import annotations

import hashlib
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.integrity_step11 import _require_active_criteria, _raw_rows, _validate_scores
from app.db.session import get_db
from app.engine.influence import analyze_influence
from app.models import AnalyticsRun, Event, User
from app.schemas.influence import InfluenceAnalysisRequest
from app.security.auth import current_user
from app.security.authorization import event_manager
from app.services.audit import record_audit
from app.services.webhooks import dispatch_event


router = APIRouter(tags=["JudgeGuard Step 12 — Influence"])


def _hash_payload(payload: dict) -> str:
    blob = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


@router.post("/events/{event_id}/judging/influence/analyze")
def analyze_event_influence(
    event_id: UUID,
    payload: InfluenceAnalysisRequest,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    rows = _raw_rows(db, event_id)
    if not rows:
        raise HTTPException(status_code=409, detail="No evaluations available for influence analysis")

    criteria = _require_active_criteria(db, event_id)
    _validate_scores(rows, criteria)
    weights = {criterion_id: data["weight"] for criterion_id, data in criteria.items()}

    result = analyze_influence(
        rows,
        weights,
        normalization_method=payload.normalization_method,
        min_observations=payload.min_observations,
        clip=payload.clip,
        max_coalition=payload.max_coalition,
        max_exact_judges=payload.max_exact_judges,
        max_reported_coalitions=payload.max_reported_coalitions,
    )

    input_payload = {
        "rows": rows,
        "criteria": criteria,
        "config": payload.model_dump(mode="json"),
    }
    input_hash = _hash_payload(input_payload)

    run = AnalyticsRun(
        event_id=event_id,
        kind="INFLUENCE",
        method="frozen_normalization_judge_removal_v1",
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
        action="INFLUENCE_ANALYSIS_COMPLETED",
        entity_type="analytics_run",
        entity_id=str(run.id),
        payload={
            "input_hash": input_hash,
            "method": run.method,
            "minimum_flip_size": result["attack_surface"]["minimum_flip_size"],
            "single_judge_flip_count": result["attack_surface"]["single_judge_flip_count"],
        },
    )
    db.commit()
    dispatch_event(
        db,
        event_id,
        "analytics.influence.completed",
        {"run_id": str(run.id), "input_hash": input_hash, "method": run.method},
    )

    return {
        "run_id": str(run.id),
        "method": run.method,
        "created_at": run.created_at,
        "result": result,
    }


@router.get("/events/{event_id}/judging/influence/latest")
def latest_influence(
    event_id: UUID,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    run = db.scalar(
        select(AnalyticsRun)
        .where(
            AnalyticsRun.event_id == event_id,
            AnalyticsRun.kind == "INFLUENCE",
        )
        .order_by(AnalyticsRun.created_at.desc())
    )
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


@router.get("/events/{event_id}/judging/influence/attack-surface")
def latest_attack_surface(
    event_id: UUID,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    run = db.scalar(
        select(AnalyticsRun)
        .where(
            AnalyticsRun.event_id == event_id,
            AnalyticsRun.kind == "INFLUENCE",
        )
        .order_by(AnalyticsRun.created_at.desc())
    )
    if run is None:
        return {"run_id": None, "attack_surface": None}

    return {
        "run_id": str(run.id),
        "attack_surface": run.result.get("attack_surface", {}),
        "baseline": run.result.get("baseline", {}),
    }
