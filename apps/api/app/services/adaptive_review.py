from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.adaptive import recommend_next_review
from app.models import (
    AssignmentStatus,
    Event,
    Evaluation,
    JudgeAssignment,
    JudgeConflict,
    JudgeProfile,
    ReviewRecommendation,
    Submission,
    SubmissionStatus,
    TeamMember,
    User,
)


def _norm_tags(values) -> set[str]:
    return {str(value).strip().lower() for value in (values or []) if str(value).strip()}


def build_adaptive_judge_candidates(
    db: Session,
    event_id: UUID,
    target_submission_ids: list[UUID],
) -> tuple[list[dict], dict[str, set[str]]]:
    targets = {
        submission_id: db.get(Submission, submission_id)
        for submission_id in target_submission_ids
    }
    targets = {
        submission_id: submission
        for submission_id, submission in targets.items()
        if submission is not None
    }
    if not targets:
        raise HTTPException(status_code=409, detail="Adaptive review targets are not available")
    for submission in targets.values():
        if submission.event_id != event_id or submission.status != SubmissionStatus.SUBMITTED:
            raise HTTPException(status_code=409, detail="Adaptive review target must be a submitted project in this event")

    profiles = db.scalars(select(JudgeProfile).where(JudgeProfile.event_id == event_id)).all()
    assignments = db.scalars(select(JudgeAssignment).where(JudgeAssignment.event_id == event_id)).all()
    conflicts = db.scalars(
        select(JudgeConflict).where(
            JudgeConflict.event_id == event_id,
            JudgeConflict.team_id.in_([submission.team_id for submission in targets.values()]),
        )
    ).all()
    team_members = db.scalars(
        select(TeamMember).where(
            TeamMember.team_id.in_([submission.team_id for submission in targets.values()])
        )
    ).all()

    conflict_by_team: dict[str, set[str]] = defaultdict(set)
    for row in conflicts:
        conflict_by_team[str(row.team_id)].add(str(row.judge_id))
    member_by_team: dict[str, set[str]] = defaultdict(set)
    for row in team_members:
        member_by_team[str(row.team_id)].add(str(row.user_id))

    by_judge: dict[str, list[JudgeAssignment]] = defaultdict(list)
    by_submission: dict[str, list[str]] = defaultdict(list)
    for assignment in assignments:
        jid = str(assignment.judge_id)
        sid = str(assignment.submission_id)
        by_judge[jid].append(assignment)
        by_submission[sid].append(jid)

    peer_projects_by_target: dict[str, set[str]] = {}
    for submission in targets.values():
        target_sid = str(submission.id)
        target_judges = set(by_submission.get(target_sid, []))
        peer_projects: set[str] = set()
        for judge_id in target_judges:
            peer_projects.update(str(row.submission_id) for row in by_judge.get(judge_id, []))
        peer_projects.discard(target_sid)
        peer_projects_by_target[target_sid] = peer_projects

    target_tags = {
        str(submission.id): _norm_tags(submission.tech_tags)
        for submission in targets.values()
    }
    candidates = []
    for profile in profiles:
        jid = str(profile.user_id)
        judge_assignments = by_judge.get(jid, [])
        assignment_count = len(judge_assignments)
        capacity = max(1, int(profile.capacity))
        load_ratio = assignment_count / capacity
        evaluated_submission_ids = {str(row.submission_id) for row in judge_assignments}

        conflicts_for_judge = {
            str(submission.id)
            for submission in targets.values()
            if jid in conflict_by_team.get(str(submission.team_id), set())
        }
        self_review_for_judge = {
            str(submission.id)
            for submission in targets.values()
            if jid in member_by_team.get(str(submission.team_id), set())
        }
        expertise = _norm_tags(profile.expertise)
        expertise_fit_by_submission = {}
        overlap_by_submission = {}
        for sid, tags in target_tags.items():
            if tags and expertise:
                expertise_fit_by_submission[sid] = len(tags & expertise) / len(tags | expertise)
            elif not tags:
                expertise_fit_by_submission[sid] = 0.5
            else:
                expertise_fit_by_submission[sid] = 0.0
            peer_projects = peer_projects_by_target.get(sid, set())
            overlap_by_submission[sid] = len(evaluated_submission_ids & peer_projects) / max(1, len(peer_projects))

        candidates.append(
            {
                "judge_id": jid,
                "capacity": capacity,
                "assignment_count": assignment_count,
                "load_ratio": load_ratio,
                "expertise": list(profile.expertise or []),
                "evaluated_submission_ids": sorted(evaluated_submission_ids),
                "conflicted_submission_ids": sorted(conflicts_for_judge),
                "team_member_submission_ids": sorted(self_review_for_judge),
                "expertise_fit_by_submission": expertise_fit_by_submission,
                "overlap_by_submission": overlap_by_submission,
            }
        )

    return candidates, target_tags


def apply_review_decision(
    db: Session,
    *,
    event: Event,
    recommendation: ReviewRecommendation,
    accept: bool,
    actor: User,
    audit_fn,
) -> dict:
    if recommendation.event_id != event.id:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if recommendation.status not in {"RECOMMENDED", "BLOCKED"}:
        raise HTTPException(status_code=409, detail="Recommendation already decided")

    if not accept:
        recommendation.status = "REJECTED"
        audit_fn(
            db,
            event_id=event.id,
            actor_user_id=actor.id,
            action="ADAPTIVE_REVIEW_REJECTED",
            entity_type="review_recommendation",
            entity_id=str(recommendation.id),
            payload={"submission_id": str(recommendation.submission_id)},
        )
        db.commit()
        return {"status": recommendation.status}

    if recommendation.recommended_judge_id is None:
        raise HTTPException(status_code=409, detail="No eligible judge is attached to this recommendation")
    now = datetime.now(timezone.utc)
    if event.judging_deadline and now > event.judging_deadline:
        raise HTTPException(status_code=409, detail="Judging deadline has passed")
    if event.judging_opens_at and now < event.judging_opens_at:
        raise HTTPException(status_code=409, detail="Judging has not opened")

    submission = db.get(Submission, recommendation.submission_id)
    if submission is None or submission.event_id != event.id or submission.status != SubmissionStatus.SUBMITTED:
        raise HTTPException(status_code=409, detail="Recommended submission is not available for review")

    profile = db.scalar(
        select(JudgeProfile).where(
            JudgeProfile.event_id == event.id,
            JudgeProfile.user_id == recommendation.recommended_judge_id,
        )
    )
    if profile is None:
        raise HTTPException(status_code=409, detail="Recommended judge is no longer configured for this event")

    team_member = db.scalar(
        select(TeamMember).where(
            TeamMember.team_id == submission.team_id,
            TeamMember.user_id == recommendation.recommended_judge_id,
        )
    )
    if team_member is not None:
        raise HTTPException(status_code=409, detail="Judge cannot review a submission from their own team")

    conflict = db.scalar(
        select(JudgeConflict).where(
            JudgeConflict.event_id == event.id,
            JudgeConflict.judge_id == recommendation.recommended_judge_id,
            JudgeConflict.team_id == submission.team_id,
        )
    )
    if conflict is not None:
        raise HTTPException(status_code=409, detail="Judge conflict blocks this review")

    existing = db.scalar(
        select(JudgeAssignment).where(
            JudgeAssignment.event_id == event.id,
            JudgeAssignment.judge_id == recommendation.recommended_judge_id,
            JudgeAssignment.submission_id == recommendation.submission_id,
        )
    )
    if existing is not None:
        recommendation.status = "ALREADY_ASSIGNED"
        db.commit()
        return {"status": recommendation.status, "assignment_id": str(existing.id)}

    assignment_count = db.query(JudgeAssignment).filter(
        JudgeAssignment.event_id == event.id,
        JudgeAssignment.judge_id == recommendation.recommended_judge_id,
    ).count()
    if assignment_count >= profile.capacity:
        raise HTTPException(status_code=409, detail="Recommended judge has no remaining capacity")

    max_position = db.query(JudgeAssignment.queue_position).filter(
        JudgeAssignment.event_id == event.id,
        JudgeAssignment.judge_id == recommendation.recommended_judge_id,
    ).order_by(JudgeAssignment.queue_position.desc()).first()
    next_position = int(max_position[0]) + 1 if max_position else 1

    assignment = JudgeAssignment(
        event_id=event.id,
        judge_id=recommendation.recommended_judge_id,
        submission_id=recommendation.submission_id,
        queue_position=next_position,
        status=AssignmentStatus.ASSIGNED,
    )
    db.add(assignment)
    db.flush()
    recommendation.status = "REVIEW_PENDING"
    audit_fn(
        db,
        event_id=event.id,
        actor_user_id=actor.id,
        action="ADAPTIVE_REVIEW_ACCEPTED",
        entity_type="review_recommendation",
        entity_id=str(recommendation.id),
        payload={
            "assignment_id": str(assignment.id),
            "submission_id": str(recommendation.submission_id),
            "judge_id": str(recommendation.recommended_judge_id),
        },
    )
    db.commit()
    return {"status": recommendation.status, "assignment_id": str(assignment.id)}


def find_assignment_evaluation(db: Session, recommendation: ReviewRecommendation) -> tuple[JudgeAssignment, Evaluation | None]:
    assignment = db.scalar(
        select(JudgeAssignment).where(
            JudgeAssignment.event_id == recommendation.event_id,
            JudgeAssignment.judge_id == recommendation.recommended_judge_id,
            JudgeAssignment.submission_id == recommendation.submission_id,
        )
    )
    if assignment is None:
        raise HTTPException(status_code=409, detail="Adaptive review assignment not found")
    evaluation = db.scalar(select(Evaluation).where(Evaluation.assignment_id == assignment.id))
    return assignment, evaluation
