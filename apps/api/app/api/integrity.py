from __future__ import annotations

import hashlib
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.engine.adaptive import recommend_next_review
from app.engine.influence import analyze_influence
from app.engine.statistics import calibration_analysis, score_drift
from app.engine.stability import analyze_stability
from app.models import (
    AnalyticsRun,
    AssignmentStatus,
    CalibrationAnchor,
    Event,
    Evaluation,
    EvaluationScore,
    JudgeAssignment,
    JudgeConflict,
    JudgeProfile,
    Submission,
    SubmissionStatus,
    User,
    UserRole,
    ReviewRecommendation,
)
from app.schemas.judging import IntegrityRunRequest, ReviewDecision
from app.security.auth import current_user
from app.security.rbac import require_roles
from app.security.authorization import event_manager
from app.services.adaptive_review import apply_review_decision, build_adaptive_judge_candidates
from app.services.audit import record_audit
from app.services.webhooks import dispatch_event

router = APIRouter(tags=["JudgeGuard Integrity"])


def _raw_rows(db: Session, event_id: UUID) -> list[dict]:
    rows = []
    evaluations = db.scalars(select(Evaluation).where(Evaluation.event_id == event_id)).all()
    queue = {str(a.id): a.queue_position for a in db.scalars(select(JudgeAssignment).where(JudgeAssignment.event_id == event_id)).all()}
    for evaluation in evaluations:
        assignment = db.get(JudgeAssignment, evaluation.assignment_id)
        for score in db.scalars(select(EvaluationScore).where(EvaluationScore.evaluation_id == evaluation.id)).all():
            rows.append(
                {
                    "judge_id": str(evaluation.judge_id),
                    "submission_id": str(evaluation.submission_id),
                    "criterion_id": str(score.criterion_id),
                    "score": float(score.score),
                    "queue_position": queue.get(str(assignment.id), 0) if assignment else 0,
                    "submitted_at": evaluation.submitted_at.isoformat() if evaluation.submitted_at else "",
                }
            )
    return rows


def _weights(db: Session, event_id: UUID) -> dict[str, float]:
    from app.models import Rubric, RubricCriterion
    rubric = db.scalar(select(Rubric).where(Rubric.event_id == event_id, Rubric.is_active.is_(True)).order_by(Rubric.version.desc()))
    if rubric is None:
        raise HTTPException(status_code=409, detail="Active rubric is required")
    criteria = db.scalars(select(RubricCriterion).where(RubricCriterion.rubric_id == rubric.id)).all()
    if not criteria:
        raise HTTPException(status_code=409, detail="Rubric has no criteria")
    total = sum(c.weight for c in criteria)
    return {str(c.id): float(c.weight / total) for c in criteria}


def _input_hash(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(blob).hexdigest()


@router.post("/events/{event_id}/integrity/run")
def run_integrity(
    event_id: UUID,
    payload: IntegrityRunRequest,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    rows = _raw_rows(db, event_id)
    if not rows:
        raise HTTPException(status_code=409, detail="No evaluations available for analysis")
    weights = _weights(db, event_id)
    stability_report = analyze_stability(
        rows,
        weights,
        normalization_method=payload.normalization_method,
        min_observations=3,
        clip=True,
        bootstrap_iterations=payload.bootstrap_iterations,
        seed=0,
        top_k=3,
        pairwise_top_n=5,
        sensitivity_delta=payload.sensitivity_delta,
        sensitivity_steps=4,
    )
    normalized_result = {
        "method": stability_report["normalization"]["method"],
        "min_observations": stability_report["normalization"]["min_observations"],
        "clip": stability_report["normalization"]["clip"],
        "diagnostics": stability_report["diagnostics"]["normalization"],
    }
    ranking = stability_report["baseline"]["ranking"]
    stability = stability_report["bootstrap"]
    influence_report = analyze_influence(
        rows,
        weights,
        normalization_method=payload.normalization_method,
        min_observations=3,
        clip=True,
        max_coalition=payload.attack_max_coalition,
        max_exact_judges=40,
        max_reported_coalitions=10,
    )
    influence = {
        "baseline_winner": influence_report["baseline"]["winner"],
        "baseline": influence_report["baseline"]["ranking"],
        "judges": influence_report["judges"],
        "attack_surface": influence_report["attack_surface"],
    }
    minimum_coalitions = influence_report["attack_surface"]["minimum_flip_coalitions"]
    first_coalition = minimum_coalitions[0] if minimum_coalitions else None
    new_winners = influence_report["attack_surface"]["new_winners_under_minimum_flip"]
    flip_set = {
        "baseline_winner": influence_report["baseline"]["winner"],
        "minimum_size": influence_report["attack_surface"]["minimum_flip_size"],
        "coalition": first_coalition,
        "new_winner": new_winners[0] if new_winners else None,
        "tested_sizes": influence_report["attack_surface"]["tested_coalition_sizes"],
        "tested_combinations": influence_report["attack_surface"]["tested_combinations"],
        "model": influence_report["model"],
    }
    sensitivity = stability_report["rubric_sensitivity"]
    drift = score_drift(rows)
    anchors = [
        {"submission_id": str(a.submission_id), "criterion_id": str(a.criterion_id), "target_score": a.target_score, "tolerance": a.tolerance}
        for a in db.scalars(select(CalibrationAnchor).where(CalibrationAnchor.event_id == event_id)).all()
    ]
    calibration = calibration_analysis(rows, anchors)

    target_id = UUID(str(ranking[0]["submission_id"])) if ranking else None
    judge_candidates, target_tags = build_adaptive_judge_candidates(db, event_id, [target_id] if target_id else []) if target_id else ([], {})
    rec = recommend_next_review(
        ranking,
        stability.get("rank1_frequency", {}),
        judge_candidates,
        coverage_frequency=stability.get("coverage_frequency", {}),
        target_rank_limit=1,
        target_tags=target_tags,
    )
    result = {
        "ranking": ranking,
        "normalization": normalized_result,
        "stability": stability,
        "influence": influence,
        "minimum_flip_set": flip_set,
        "rubric_sensitivity": sensitivity,
        "score_drift": drift,
        "calibration": calibration,
        "adaptive_review": rec,
    }
    input_hash = _input_hash({"rows": rows, "weights": weights, "config": payload.model_dump(mode="json")})
    run = AnalyticsRun(event_id=event_id, kind="INTEGRITY", method="JudgeGuard-v1", input_hash=input_hash, result=result, created_by=user.id)
    db.add(run)
    record_audit(db, event_id=event_id, actor_user_id=user.id, action="INTEGRITY_RUN_COMPLETED", entity_type="analytics_run", entity_id=str(run.id), payload={"input_hash": input_hash})
    db.commit()
    dispatch_event(db, event_id, "analytics.integrity.completed", {"run_id": str(run.id), "input_hash": input_hash})

    if rec and rec.get("judge_id"):
        db.add(
            ReviewRecommendation(
                event_id=event_id,
                submission_id=UUID(str(rec["submission_id"])),
                recommended_judge_id=UUID(str(rec["judge_id"])),
                reason=rec["reason"],
                expected_gain=float(rec["expected_gain"]),
            )
        )
        db.commit()

    return {"run_id": str(run.id), "result": result}


@router.get("/events/{event_id}/integrity/latest")
def latest_integrity(event_id: UUID, event: Event = Depends(event_manager), db: Session = Depends(get_db), user: User = Depends(current_user)):
    run = db.scalar(select(AnalyticsRun).where(AnalyticsRun.event_id == event_id, AnalyticsRun.kind == "INTEGRITY").order_by(AnalyticsRun.created_at.desc()))
    if run is None:
        return {"run": None}
    return {"run": {"id": str(run.id), "created_at": run.created_at, "method": run.method, "input_hash": run.input_hash, "result": run.result}}


@router.get("/events/{event_id}/integrity/recommendations")
def recommendations(event_id: UUID, event: Event = Depends(event_manager), db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(select(ReviewRecommendation).where(ReviewRecommendation.event_id == event_id).order_by(ReviewRecommendation.created_at.desc())).all()
    return [
        {"id": str(r.id), "submission_id": str(r.submission_id), "recommended_judge_id": str(r.recommended_judge_id) if r.recommended_judge_id else None, "reason": r.reason, "expected_gain": r.expected_gain, "status": r.status, "created_at": r.created_at}
        for r in rows
    ]


@router.post("/events/{event_id}/integrity/recommendations/{recommendation_id}")
def decide_recommendation(
    event_id: UUID,
    recommendation_id: UUID,
    payload: ReviewDecision,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    rec = db.get(ReviewRecommendation, recommendation_id)
    if rec is None or rec.event_id != event_id:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return apply_review_decision(
        db,
        event=event,
        recommendation=rec,
        accept=payload.accept,
        actor=user,
        audit_fn=record_audit,
    )
