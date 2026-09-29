from __future__ import annotations

import hashlib
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.integrity import _raw_rows
from app.db.session import get_db
from app.engine.normalization import calibration_metrics, drift_metrics, normalize_by_judge_criterion
from app.models import AnalyticsRun, CalibrationAnchor, Event, Rubric, RubricCriterion, User
from app.schemas.integrity import (
    CalibrationAnalysisRequest,
    DriftAnalysisRequest,
    NormalizationRunRequest,
)
from app.security.auth import current_user
from app.security.authorization import event_manager
from app.services.audit import record_audit
from app.services.webhooks import dispatch_event


router = APIRouter(tags=["JudgeGuard Step 11"])


def _hash_payload(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _require_active_criteria(db: Session, event_id: UUID) -> dict[str, dict]:
    rubric = db.scalar(
        select(Rubric)
        .where(Rubric.event_id == event_id, Rubric.is_active.is_(True))
        .order_by(Rubric.version.desc())
    )
    if rubric is None:
        raise HTTPException(status_code=409, detail="Active rubric is required")

    criteria = list(
        db.scalars(
            select(RubricCriterion).where(RubricCriterion.rubric_id == rubric.id)
        ).all()
    )
    if not criteria:
        raise HTTPException(status_code=409, detail="Active rubric has no criteria")

    total_weight = sum(float(c.weight) for c in criteria)
    if total_weight <= 0:
        raise HTTPException(status_code=409, detail="Active rubric has invalid weights")

    return {
        str(c.id): {
            "name": c.name,
            "min_score": float(c.min_score),
            "max_score": float(c.max_score),
            "weight": float(c.weight) / total_weight,
        }
        for c in criteria
    }


def _validate_scores(rows: list[dict], criteria: dict[str, dict]) -> None:
    unknown = sorted({str(r["criterion_id"]) for r in rows if str(r["criterion_id"]) not in criteria})
    if unknown:
        raise HTTPException(
            status_code=409,
            detail=f"Evaluations contain criteria outside the active rubric: {unknown}",
        )

    for row in rows:
        criterion = criteria[str(row["criterion_id"])]
        score = float(row["score"])
        if score < criterion["min_score"] or score > criterion["max_score"]:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Score {score} is outside the allowed range "
                    f"[{criterion['min_score']}, {criterion['max_score']}] "
                    f"for criterion '{criterion['name']}'."
                ),
            )


def _anchors(db: Session, event_id: UUID) -> list[dict]:
    return [
        {
            "submission_id": str(anchor.submission_id),
            "criterion_id": str(anchor.criterion_id),
            "target_score": float(anchor.target_score),
            "tolerance": float(anchor.tolerance),
        }
        for anchor in db.scalars(
            select(CalibrationAnchor).where(CalibrationAnchor.event_id == event_id)
        ).all()
    ]


@router.post("/events/{event_id}/judging/normalization/run")
def run_step11_normalization(
    event_id: UUID,
    payload: NormalizationRunRequest,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    rows = _raw_rows(db, event_id)
    if not rows:
        raise HTTPException(status_code=409, detail="No evaluations available for normalization")

    criteria = _require_active_criteria(db, event_id)
    _validate_scores(rows, criteria)

    result = normalize_by_judge_criterion(
        rows,
        method=payload.normalization_method,
        min_observations=payload.min_observations,
        clip=payload.clip,
    )

    input_payload = {
        "rows": rows,
        "criteria": criteria,
        "config": payload.model_dump(mode="json"),
    }
    input_hash = _hash_payload(input_payload)

    run = AnalyticsRun(
        event_id=event_id,
        kind="NORMALIZATION",
        method=f"judge_criterion_{payload.normalization_method}",
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
        action="NORMALIZATION_RUN_COMPLETED",
        entity_type="analytics_run",
        entity_id=str(run.id),
        payload={"input_hash": input_hash, "method": run.method},
    )
    db.commit()
    dispatch_event(
        db,
        event_id,
        "analytics.normalization.completed",
        {"run_id": str(run.id), "input_hash": input_hash, "method": run.method},
    )

    return {
        "run_id": str(run.id),
        "method": run.method,
        "created_at": run.created_at,
        "result": result,
    }


@router.get("/events/{event_id}/judging/normalization/runs")
def normalization_runs(
    event_id: UUID,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    runs = list(
        db.scalars(
            select(AnalyticsRun)
            .where(
                AnalyticsRun.event_id == event_id,
                AnalyticsRun.kind == "NORMALIZATION",
            )
            .order_by(AnalyticsRun.created_at.desc())
        ).all()
    )
    return [
        {
            "id": str(run.id),
            "method": run.method,
            "input_hash": run.input_hash,
            "created_at": run.created_at,
            "diagnostics": run.result.get("diagnostics", {}),
        }
        for run in runs
    ]


@router.post("/events/{event_id}/judging/calibration/analyze")
def analyze_calibration(
    event_id: UUID,
    payload: CalibrationAnalysisRequest,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    rows = _raw_rows(db, event_id)
    if not rows:
        raise HTTPException(status_code=409, detail="No evaluations available for calibration analysis")

    criteria = _require_active_criteria(db, event_id)
    _validate_scores(rows, criteria)
    result = calibration_metrics(
        rows,
        anchors=_anchors(db, event_id),
        min_observations=payload.min_observations,
    )
    input_hash = _hash_payload({"rows": rows, "config": payload.model_dump(mode="json")})

    run = AnalyticsRun(
        event_id=event_id,
        kind="CALIBRATION",
        method="judge_criterion_calibration_v1",
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
        action="CALIBRATION_ANALYSIS_COMPLETED",
        entity_type="analytics_run",
        entity_id=str(run.id),
        payload={"input_hash": input_hash},
    )
    db.commit()
    dispatch_event(
        db,
        event_id,
        "analytics.calibration.completed",
        {"run_id": str(run.id), "input_hash": input_hash, "method": run.method},
    )

    return {"run_id": str(run.id), "result": result}


@router.get("/events/{event_id}/judging/calibration/latest")
def latest_calibration(
    event_id: UUID,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    run = db.scalar(
        select(AnalyticsRun)
        .where(AnalyticsRun.event_id == event_id, AnalyticsRun.kind == "CALIBRATION")
        .order_by(AnalyticsRun.created_at.desc())
    )
    if run is None:
        return {"run": None}
    return {
        "run": {
            "id": str(run.id),
            "method": run.method,
            "input_hash": run.input_hash,
            "created_at": run.created_at,
            "result": run.result,
        }
    }


@router.post("/events/{event_id}/judging/drift/analyze")
def analyze_drift(
    event_id: UUID,
    payload: DriftAnalysisRequest,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    rows = _raw_rows(db, event_id)
    if not rows:
        raise HTTPException(status_code=409, detail="No evaluations available for drift analysis")

    criteria = _require_active_criteria(db, event_id)
    _validate_scores(rows, criteria)
    result = drift_metrics(rows, min_observations=payload.min_observations)
    result["min_observations"] = payload.min_observations
    input_hash = _hash_payload({"rows": rows, "config": payload.model_dump(mode="json")})

    run = AnalyticsRun(
        event_id=event_id,
        kind="DRIFT",
        method="judge_criterion_queue_drift_v1",
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
        action="DRIFT_ANALYSIS_COMPLETED",
        entity_type="analytics_run",
        entity_id=str(run.id),
        payload={"input_hash": input_hash},
    )
    db.commit()
    dispatch_event(
        db,
        event_id,
        "analytics.drift.completed",
        {"run_id": str(run.id), "input_hash": input_hash, "method": run.method},
    )

    return {"run_id": str(run.id), "result": result}


@router.get("/events/{event_id}/judging/drift/latest")
def latest_drift(
    event_id: UUID,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    run = db.scalar(
        select(AnalyticsRun)
        .where(AnalyticsRun.event_id == event_id, AnalyticsRun.kind == "DRIFT")
        .order_by(AnalyticsRun.created_at.desc())
    )
    if run is None:
        return {"run": None}
    return {
        "run": {
            "id": str(run.id),
            "method": run.method,
            "input_hash": run.input_hash,
            "created_at": run.created_at,
            "result": run.result,
        }
    }
