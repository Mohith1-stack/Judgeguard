from __future__ import annotations

import hashlib
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.integrity import _raw_rows, _weights
from app.db.session import get_db
from app.engine.adaptive import recommend_next_review
from app.engine.influence import analyze_influence
from app.engine.stability import analyze_stability
from app.models import AnalyticsRun, Event, ReviewRecommendation, Submission, User
from app.schemas.adaptive import AdaptiveRecalculateRequest, AdaptiveReviewRequest
from app.schemas.judging import ReviewDecision
from app.security.auth import current_user
from app.security.authorization import event_manager
from app.services.adaptive_review import (
    apply_review_decision,
    build_adaptive_judge_candidates,
    find_assignment_evaluation,
)
from app.services.audit import record_audit
from app.services.webhooks import dispatch_event


router = APIRouter(tags=["JudgeGuard Step 14 — Adaptive Review"])


def _hash_payload(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _latest_run(db: Session, event_id: UUID, kind: str) -> AnalyticsRun | None:
    return db.scalar(
        select(AnalyticsRun)
        .where(AnalyticsRun.event_id == event_id, AnalyticsRun.kind == kind)
        .order_by(AnalyticsRun.created_at.desc())
    )


def _find_source_adaptive_run(db: Session, event_id: UUID, recommendation_id: UUID) -> AnalyticsRun | None:
    runs = db.scalars(
        select(AnalyticsRun)
        .where(AnalyticsRun.event_id == event_id, AnalyticsRun.kind == "ADAPTIVE_REVIEW")
        .order_by(AnalyticsRun.created_at.desc())
        .limit(100)
    ).all()
    target = str(recommendation_id)
    for run in runs:
        if str(run.result.get("recommendation", {}).get("id")) == target:
            return run
    return None


def _recommendation_payload(rec: ReviewRecommendation) -> dict:
    return {
        "id": str(rec.id),
        "submission_id": str(rec.submission_id),
        "recommended_judge_id": str(rec.recommended_judge_id) if rec.recommended_judge_id else None,
        "reason": rec.reason,
        "expected_gain": rec.expected_gain,
        "status": rec.status,
        "created_at": rec.created_at,
    }


@router.post("/events/{event_id}/judging/adaptive-review/recommend")
def generate_adaptive_review(
    event_id: UUID,
    payload: AdaptiveReviewRequest,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    stability_run = _latest_run(db, event_id, "STABILITY")
    if stability_run is None:
        raise HTTPException(status_code=409, detail="Run ranking stability before requesting adaptive review")

    stability = stability_run.result
    ranking = stability.get("baseline", {}).get("ranking", [])
    if not ranking:
        raise HTTPException(status_code=409, detail="Ranking stability run contains no ranking")

    excluded_rows = db.scalars(
        select(ReviewRecommendation).where(
            ReviewRecommendation.event_id == event_id,
            ReviewRecommendation.status.in_(["RECOMMENDED", "REVIEW_PENDING"]),
        )
    ).all()
    excluded_submissions = {str(row.submission_id) for row in excluded_rows}
    target_ids = [UUID(str(item["submission_id"])) for item in ranking[: payload.target_rank_limit] if str(item["submission_id"]) not in excluded_submissions]
    if not target_ids:
        raise HTTPException(status_code=409, detail="All top-ranked projects already have an open adaptive-review recommendation")

    judge_candidates, target_tags = build_adaptive_judge_candidates(db, event_id, target_ids)
    influence_run = _latest_run(db, event_id, "INFLUENCE")
    attack_surface = (influence_run.result or {}).get("attack_surface", {}) if influence_run else {}
    fragile_submissions = {str(x) for x in attack_surface.get("new_winners_under_minimum_flip", [])}

    analysis_config = {
        "normalization_method": stability.get("normalization", {}).get("method", "robust_zscore"),
        "min_observations": stability.get("normalization", {}).get("min_observations", 3),
        "clip": stability.get("normalization", {}).get("clip", True),
    }

    recommendation = recommend_next_review(
        ranking,
        stability.get("bootstrap", {}).get("rank1_frequency", {}),
        judge_candidates,
        coverage_frequency=stability.get("bootstrap", {}).get("coverage_frequency", {}),
        fragile_submissions=fragile_submissions,
        excluded_submissions=excluded_submissions,
        target_rank_limit=payload.target_rank_limit,
        max_candidates=payload.max_candidates,
        minimum_priority=payload.minimum_priority,
        target_tags=target_tags,
    )
    if recommendation is None:
        raise HTTPException(status_code=409, detail="No target met the configured adaptive-review priority")

    rec = ReviewRecommendation(
        event_id=event_id,
        submission_id=UUID(str(recommendation["submission_id"])),
        recommended_judge_id=(UUID(str(recommendation["judge_id"])) if recommendation.get("judge_id") else None),
        reason=recommendation["reason"],
        expected_gain=float(recommendation["expected_gain"]),
        status="RECOMMENDED" if recommendation.get("judge_id") else "BLOCKED",
    )
    db.add(rec)
    db.flush()

    input_payload = {
        "stability_run_id": str(stability_run.id),
        "influence_run_id": str(influence_run.id) if influence_run else None,
        "ranking": ranking,
        "rank1_frequency": stability.get("bootstrap", {}).get("rank1_frequency", {}),
        "coverage_frequency": stability.get("bootstrap", {}).get("coverage_frequency", {}),
        "judge_candidates": judge_candidates,
        "config": payload.model_dump(mode="json"),
    }
    input_hash = _hash_payload(input_payload)
    run = AnalyticsRun(
        event_id=event_id,
        kind="ADAPTIVE_REVIEW",
        method=recommendation["model"],
        input_hash=input_hash,
        result={
            "recommendation": {
                **recommendation,
                "id": str(rec.id),
            },
            "analysis_config": analysis_config,
            "source_stability_run_id": str(stability_run.id),
            "source_influence_run_id": str(influence_run.id) if influence_run else None,
            "baseline_winner": ranking[0].get("submission_id"),
            "baseline_ranking": ranking,
            "input_hash": input_hash,
        },
        created_by=user.id,
    )
    db.add(run)
    db.flush()
    record_audit(
        db,
        event_id=event_id,
        actor_user_id=user.id,
        action="ADAPTIVE_REVIEW_RECOMMENDED",
        entity_type="review_recommendation",
        entity_id=str(rec.id),
        payload={
            "analytics_run_id": str(run.id),
            "submission_id": str(rec.submission_id),
            "judge_id": str(rec.recommended_judge_id) if rec.recommended_judge_id else None,
            "expected_gain": rec.expected_gain,
            "input_hash": input_hash,
        },
    )
    db.commit()
    dispatch_event(db, event_id, "adaptive_review.recommended", {"recommendation_id": str(rec.id), "submission_id": str(rec.submission_id), "judge_id": str(rec.recommended_judge_id) if rec.recommended_judge_id else None})

    response_recommendation = {**recommendation, "id": str(rec.id), "status": rec.status}
    return {
        "recommendation": response_recommendation,
        "recommendation_id": str(rec.id),
        "analytics_run_id": str(run.id),
        "source_stability_run_id": str(stability_run.id),
        "source_influence_run_id": str(influence_run.id) if influence_run else None,
    }


@router.get("/events/{event_id}/judging/adaptive-review/latest")
def latest_adaptive_review(
    event_id: UUID,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    run = _latest_run(db, event_id, "ADAPTIVE_REVIEW")
    result_run = None
    if run is not None:
        recommendation_id = str(run.result.get("recommendation", {}).get("id"))
        result_runs = db.scalars(
            select(AnalyticsRun)
            .where(AnalyticsRun.event_id == event_id, AnalyticsRun.kind == "ADAPTIVE_REVIEW_RESULT")
            .order_by(AnalyticsRun.created_at.desc())
            .limit(100)
        ).all()
        result_run = next(
            (candidate for candidate in result_runs if str(candidate.result.get("recommendation_id")) == recommendation_id),
            None,
        )
    return {
        "run": None if run is None else {
            "id": str(run.id),
            "created_at": run.created_at,
            "method": run.method,
            "input_hash": run.input_hash,
            "result": run.result,
        },
        "latest_recalculation": None if result_run is None else {
            "id": str(result_run.id),
            "created_at": result_run.created_at,
            "result": result_run.result,
        },
    }


@router.get("/events/{event_id}/judging/adaptive-review/recommendations")
def adaptive_review_recommendations(
    event_id: UUID,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    rows = db.scalars(
        select(ReviewRecommendation)
        .where(ReviewRecommendation.event_id == event_id)
        .order_by(ReviewRecommendation.created_at.desc())
        .limit(50)
    ).all()
    return [_recommendation_payload(row) for row in rows]


@router.post("/events/{event_id}/judging/adaptive-review/recommendations/{recommendation_id}/decision")
def decide_adaptive_review(
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


@router.post("/events/{event_id}/judging/adaptive-review/recommendations/{recommendation_id}/recalculate")
def recalculate_adaptive_review(
    event_id: UUID,
    recommendation_id: UUID,
    payload: AdaptiveRecalculateRequest,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    rec = db.get(ReviewRecommendation, recommendation_id)
    if rec is None or rec.event_id != event_id:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if rec.status != "REVIEW_PENDING":
        raise HTTPException(status_code=409, detail="Recommendation must have an accepted review awaiting evaluation")

    assignment, evaluation = find_assignment_evaluation(db, rec)
    if evaluation is None:
        raise HTTPException(status_code=409, detail="The adaptive review must be submitted by the judge before recalculation")

    source_run = _find_source_adaptive_run(db, event_id, rec.id)
    source_result = source_run.result if source_run else {}
    source_config = source_result.get("analysis_config", {})
    normalization_method = source_config.get("normalization_method", "robust_zscore")
    min_observations = int(source_config.get("min_observations", 3))
    clip = bool(source_config.get("clip", True))

    rows = _raw_rows(db, event_id)
    weights = _weights(db, event_id)
    stability = analyze_stability(
        rows,
        weights,
        normalization_method=normalization_method,
        min_observations=min_observations,
        clip=clip,
        bootstrap_iterations=payload.bootstrap_iterations,
        seed=0,
        top_k=3,
        pairwise_top_n=5,
        sensitivity_delta=payload.sensitivity_delta,
        sensitivity_steps=4,
    )
    influence = analyze_influence(
        rows,
        weights,
        normalization_method=normalization_method,
        min_observations=min_observations,
        clip=clip,
        max_coalition=payload.attack_max_coalition,
        max_exact_judges=40,
        max_reported_coalitions=10,
    )

    before_ranking = source_result.get("baseline_ranking", [])
    after_ranking = stability.get("baseline", {}).get("ranking", [])
    before_target = next((item for item in before_ranking if str(item.get("submission_id")) == str(rec.submission_id)), None)
    after_target = next((item for item in after_ranking if str(item.get("submission_id")) == str(rec.submission_id)), None)

    result = {
        "model": "post-review-recalculation-v1",
        "recommendation_id": str(rec.id),
        "assignment_id": str(assignment.id),
        "evaluation_id": str(evaluation.id),
        "before": {
            "analytics_run_id": str(source_run.id) if source_run else None,
            "winner": source_result.get("baseline_winner"),
            "target": before_target,
        },
        "after": {
            "winner": after_ranking[0].get("submission_id") if after_ranking else None,
            "target": after_target,
            "stability_rank1_frequency": stability.get("bootstrap", {}).get("rank1_frequency", {}).get(str(rec.submission_id)),
            "influence_attack_surface": influence.get("attack_surface", {}),
        },
        "stability": stability,
        "influence": influence,
        "configuration": {
            "normalization_method": normalization_method,
            "min_observations": min_observations,
            "clip": clip,
            "bootstrap_iterations": payload.bootstrap_iterations,
            "attack_max_coalition": payload.attack_max_coalition,
            "sensitivity_delta": payload.sensitivity_delta,
        },
    }
    input_hash = _hash_payload(
        {
            "rows": rows,
            "weights": weights,
            "recommendation_id": str(rec.id),
            "assignment_id": str(assignment.id),
            "evaluation_id": str(evaluation.id),
            "configuration": result["configuration"],
        }
    )
    run = AnalyticsRun(
        event_id=event_id,
        kind="ADAPTIVE_REVIEW_RESULT",
        method="post_review_recalculation_v1",
        input_hash=input_hash,
        result={**result, "input_hash": input_hash},
        created_by=user.id,
    )
    db.add(run)
    rec.status = "COMPLETED"
    record_audit(
        db,
        event_id=event_id,
        actor_user_id=user.id,
        action="ADAPTIVE_REVIEW_RECALCULATED",
        entity_type="analytics_run",
        entity_id=str(run.id),
        payload={
            "recommendation_id": str(rec.id),
            "assignment_id": str(assignment.id),
            "evaluation_id": str(evaluation.id),
            "before_winner": result["before"]["winner"],
            "after_winner": result["after"]["winner"],
            "input_hash": input_hash,
        },
    )
    db.commit()
    dispatch_event(db, event_id, "adaptive_review.recalculated", {"run_id": str(run.id), "recommendation_id": str(rec.id), "status": rec.status})

    return {"run_id": str(run.id), "recommendation_id": str(rec.id), "status": rec.status, "result": result}
