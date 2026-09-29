from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.engine.assignment import build_assignment_plan
from app.engine.statistics import aggregate_rankings, normalize_scores
from app.models import (
    AssignmentStatus,
    Event,
    Evaluation,
    EvaluationScore,
    JudgeAssignment,
    JudgeConflict,
    JudgeInvite,
    JudgeProfile,
    Rubric,
    RubricCriterion,
    Submission,
    SubmissionStatus,
    Team,
    TeamMember,
    User,
    UserRole,
    AnalyticsRun,
)
from app.schemas.judging import (
    AssignmentRequest,
    ConflictCreate,
    CriterionCreate,
    EvaluationIn,
    JudgeAssignmentOut,
    JudgeInviteCreate,
    JudgeProfileCreate,
    RubricCreate,
)
from app.security.auth import current_user
from app.security.rbac import require_roles
from app.security.authorization import event_manager
from app.services.audit import record_audit
from app.services.deadlines import is_judging_open
from app.services.webhooks import dispatch_event

router = APIRouter(tags=["Judging"])


def _load_active_rubric(db: Session, event_id: UUID) -> Rubric:
    rubric = db.scalar(
        select(Rubric)
        .where(Rubric.event_id == event_id, Rubric.is_active.is_(True))
        .order_by(Rubric.version.desc())
    )
    if rubric is None:
        raise HTTPException(status_code=409, detail="An active rubric is required")
    return rubric


def _weights(db: Session, rubric_id: UUID) -> dict[str, float]:
    criteria = db.scalars(select(RubricCriterion).where(RubricCriterion.rubric_id == rubric_id)).all()
    if not criteria:
        raise HTTPException(status_code=409, detail="Rubric has no criteria")
    total = sum(c.weight for c in criteria)
    if total <= 0:
        raise HTTPException(status_code=409, detail="Rubric weights must be positive")
    if abs(total - 1.0) > 0.001:
        raise HTTPException(status_code=409, detail="Rubric weights must sum to 1.0")
    return {str(c.id): c.weight for c in criteria}


@router.post("/events/{event_id}/judge-invites", status_code=201)
def create_judge_invite(
    payload: JudgeInviteCreate,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    invite = JudgeInvite(
        event_id=event.id,
        invited_email=payload.invited_email.strip().lower(),
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=payload.expires_hours),
        capacity=payload.capacity,
        expertise=[x.strip().lower() for x in payload.expertise if x.strip()],
    )
    db.add(invite)
    db.commit()
    dispatch_event(db, event.id, "judge.invite.created", {"judge_invite_id": str(invite.id), "invited_email": invite.invited_email, "expires_at": invite.expires_at.isoformat()})
    return {"token": token, "expires_at": invite.expires_at}


@router.post("/judge-invites/{token}/accept", status_code=201)
def accept_judge_invite(token: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    invite = db.scalar(select(JudgeInvite).where(JudgeInvite.token_hash == token_hash))
    if invite is None:
        raise HTTPException(status_code=404, detail="Judge invitation not found")
    if invite.accepted_at is not None or invite.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Judge invitation expired or already accepted")
    if user.email.lower() != invite.invited_email.lower():
        raise HTTPException(status_code=403, detail="Invitation was issued for another email")

    user.role = UserRole.JUDGE
    existing = db.scalar(select(JudgeProfile).where(JudgeProfile.event_id == invite.event_id, JudgeProfile.user_id == user.id))
    if existing is None:
        db.add(JudgeProfile(event_id=invite.event_id, user_id=user.id, capacity=invite.capacity, expertise=invite.expertise or []))
    invite.accepted_at = datetime.now(timezone.utc)
    db.commit()
    dispatch_event(db, invite.event_id, "judge.invite.accepted", {"judge_id": str(user.id)})
    return {"event_id": str(invite.event_id), "role": user.role.value}


@router.post("/events/{event_id}/judges", status_code=201)
def add_judge_profile(
    payload: JudgeProfileCreate,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    target = db.get(User, payload.user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Judge user not found")
    if target.id == event.organizer_id and target.role != UserRole.ADMIN:
        raise HTTPException(status_code=409, detail="Organizer cannot be used as a judge through this endpoint")
    target.role = UserRole.JUDGE
    existing = db.scalar(select(JudgeProfile).where(JudgeProfile.event_id == event.id, JudgeProfile.user_id == target.id))
    if existing:
        existing.capacity = payload.capacity
        existing.expertise = [x.strip().lower() for x in payload.expertise if x.strip()]
    else:
        db.add(JudgeProfile(event_id=event.id, user_id=target.id, capacity=payload.capacity, expertise=[x.strip().lower() for x in payload.expertise if x.strip()]))
    record_audit(db, event_id=event.id, actor_user_id=user.id, action="JUDGE_PROFILE_UPSERTED", entity_type="user", entity_id=str(target.id))
    db.commit()
    dispatch_event(db, event.id, "judge.profile.upserted", {"judge_id": str(target.id), "capacity": payload.capacity})
    return {"user_id": str(target.id), "role": target.role.value}


@router.post("/events/{event_id}/judge-conflicts", status_code=201)
def add_conflict(
    payload: ConflictCreate,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if db.get(User, payload.judge_id) is None or db.get(Team, payload.team_id) is None:
        raise HTTPException(status_code=404, detail="Judge or team not found")
    existing = db.scalar(select(JudgeConflict).where(JudgeConflict.event_id == event.id, JudgeConflict.judge_id == payload.judge_id, JudgeConflict.team_id == payload.team_id))
    if existing:
        return {"id": str(existing.id), "status": "exists"}
    row = JudgeConflict(event_id=event.id, judge_id=payload.judge_id, team_id=payload.team_id, reason=payload.reason)
    db.add(row)
    record_audit(db, event_id=event.id, actor_user_id=user.id, action="JUDGE_CONFLICT_CREATED", entity_type="judge_conflict", entity_id=str(row.id))
    db.commit()
    dispatch_event(db, event.id, "judge.conflict.created", {"conflict_id": str(row.id), "judge_id": str(payload.judge_id), "team_id": str(payload.team_id)})
    return {"id": str(row.id)}


@router.post("/events/{event_id}/rubrics", status_code=201)
def create_rubric(
    payload: RubricCreate,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    active = db.scalars(select(Rubric).where(Rubric.event_id == event.id, Rubric.is_active.is_(True))).all()
    for item in active:
        item.is_active = False
    version = (db.scalar(select(Rubric.version).where(Rubric.event_id == event.id).order_by(Rubric.version.desc()).limit(1)) or 0) + 1
    rubric = Rubric(event_id=event.id, name=payload.name.strip(), version=int(version), is_active=True)
    db.add(rubric)
    db.flush()
    record_audit(db, event_id=event.id, actor_user_id=user.id, action="RUBRIC_CREATED", entity_type="rubric", entity_id=str(rubric.id))
    db.commit()
    dispatch_event(db, event.id, "rubric.created", {"rubric_id": str(rubric.id), "version": rubric.version})
    return {"id": str(rubric.id), "version": rubric.version}


@router.post("/rubrics/{rubric_id}/criteria", status_code=201)
def add_criterion(
    rubric_id: UUID,
    payload: CriterionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN)),
):
    rubric = db.get(Rubric, rubric_id)
    if rubric is None:
        raise HTTPException(status_code=404, detail="Rubric not found")
    event = db.get(Event, rubric.event_id)
    if user.role != UserRole.ADMIN and event.organizer_id != user.id:
        raise HTTPException(status_code=403, detail="Organizer access required")
    if payload.min_score >= payload.max_score:
        raise HTTPException(status_code=422, detail="min_score must be lower than max_score")
    criterion = RubricCriterion(rubric_id=rubric.id, name=payload.name.strip(), description=payload.description, weight=payload.weight, min_score=payload.min_score, max_score=payload.max_score, sort_order=payload.sort_order)
    db.add(criterion)
    db.commit()
    dispatch_event(db, event.id, "rubric.criterion.created", {"criterion_id": str(criterion.id), "rubric_id": str(rubric.id)})
    return {"id": str(criterion.id), "weight": criterion.weight}


@router.post("/events/{event_id}/judging/assign", response_model=list[JudgeAssignmentOut])
def assign_judges(
    payload: AssignmentRequest,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    existing = db.scalar(select(JudgeAssignment).join(Submission).where(JudgeAssignment.event_id == event.id))
    if existing:
        raise HTTPException(status_code=409, detail="Assignments already exist; create a fresh event or clear assignments before regenerating")

    submissions = db.scalars(select(Submission).where(Submission.event_id == event.id, Submission.status == SubmissionStatus.SUBMITTED)).all()
    if not submissions:
        raise HTTPException(status_code=409, detail="No submitted projects are available")
    profiles = db.scalars(select(JudgeProfile).where(JudgeProfile.event_id == event.id)).all()
    if not profiles:
        raise HTTPException(status_code=409, detail="No judges configured")

    conflicts = {(str(c.judge_id), str(c.team_id)) for c in db.scalars(select(JudgeConflict).where(JudgeConflict.event_id == event.id)).all()}
    judge_inputs = []
    for p in profiles:
        judge_inputs.append({"id": str(p.user_id), "capacity": p.capacity, "expertise": p.expertise or []})
    submission_inputs = [{"id": str(s.id), "team_id": str(s.team_id), "track_id": str(s.track_id) if s.track_id else None, "tech_tags": s.tech_tags or []} for s in submissions]

    plan = build_assignment_plan(submission_inputs, judge_inputs, conflicts, payload.reviews_per_submission, seed=payload.seed)
    created = []
    for item in plan["assignments"]:
        row = JudgeAssignment(event_id=event.id, judge_id=UUID(item["judge_id"]), submission_id=UUID(item["submission_id"]), queue_position=item["queue_position"], status=AssignmentStatus.ASSIGNED)
        db.add(row)
        created.append(row)
    record_audit(db, event_id=event.id, actor_user_id=user.id, action="JUDGING_ASSIGNMENTS_CREATED", entity_type="assignment_batch", entity_id=str(event.id), payload={"reviews_per_submission": payload.reviews_per_submission, "seed": payload.seed, "count": len(created)})
    db.commit()
    dispatch_event(db, event.id, "judging.assignments.created", {"count": len(created), "reviews_per_submission": payload.reviews_per_submission, "seed": payload.seed})
    return [JudgeAssignmentOut(id=x.id, judge_id=x.judge_id, submission_id=x.submission_id, queue_position=x.queue_position, status=x.status.value) for x in created]


@router.get("/events/{event_id}/judging/me", response_model=list[JudgeAssignmentOut])
def my_assignments(event_id: UUID, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.JUDGE, UserRole.ORGANIZER, UserRole.ADMIN))):
    rows = db.scalars(select(JudgeAssignment).where(JudgeAssignment.event_id == event_id, JudgeAssignment.judge_id == user.id).order_by(JudgeAssignment.queue_position)).all()
    return [JudgeAssignmentOut(id=x.id, judge_id=x.judge_id, submission_id=x.submission_id, queue_position=x.queue_position, status=x.status.value) for x in rows]


@router.get("/events/{event_id}/judging/submission/{submission_id}")
def judge_submission(event_id: UUID, submission_id: UUID, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.JUDGE, UserRole.ORGANIZER, UserRole.ADMIN))):
    assignment = db.scalar(select(JudgeAssignment).where(JudgeAssignment.event_id == event_id, JudgeAssignment.submission_id == submission_id, JudgeAssignment.judge_id == user.id))
    if assignment is None:
        raise HTTPException(status_code=403, detail="This project is not assigned to you")
    submission = db.get(Submission, submission_id)
    rubric = _load_active_rubric(db, event_id)
    criteria = db.scalars(select(RubricCriterion).where(RubricCriterion.rubric_id == rubric.id).order_by(RubricCriterion.sort_order, RubricCriterion.id)).all()
    existing = db.scalar(select(Evaluation).where(Evaluation.assignment_id == assignment.id))
    return {
        "assignment": {"id": str(assignment.id), "queue_position": assignment.queue_position},
        "submission": {"id": str(submission.id), "name": submission.name, "tagline": submission.tagline, "description": submission.description, "repository_url": submission.repository_url, "live_url": submission.live_url, "demo_video_url": submission.demo_video_url, "tech_tags": submission.tech_tags or []},
        "rubric": [{"id": str(c.id), "name": c.name, "description": c.description, "weight": c.weight, "min_score": c.min_score, "max_score": c.max_score} for c in criteria],
        "already_submitted": existing is not None,
    }


@router.post("/events/{event_id}/judging/assignments/{assignment_id}/evaluation")
def submit_evaluation(event_id: UUID, assignment_id: UUID, payload: EvaluationIn, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.JUDGE, UserRole.ORGANIZER, UserRole.ADMIN))):
    assignment = db.scalar(select(JudgeAssignment).where(JudgeAssignment.id == assignment_id, JudgeAssignment.event_id == event_id))
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if user.role == UserRole.JUDGE and assignment.judge_id != user.id:
        raise HTTPException(status_code=403, detail="You may only evaluate your own assignments")
    event = db.get(Event, event_id)
    if event is None or not is_judging_open(event):
        raise HTTPException(status_code=409, detail="Judging window is closed")
    if db.scalar(select(Evaluation).where(Evaluation.assignment_id == assignment.id)) is not None:
        raise HTTPException(status_code=409, detail="Evaluation already submitted")

    rubric = _load_active_rubric(db, event_id)
    criteria = db.scalars(select(RubricCriterion).where(RubricCriterion.rubric_id == rubric.id)).all()
    expected = {str(c.id): c for c in criteria}
    submitted = {str(item.criterion_id): item for item in payload.scores}
    if set(submitted) != set(expected):
        raise HTTPException(status_code=422, detail="Every rubric criterion must receive exactly one score")
    for criterion_id, item in submitted.items():
        criterion = expected[criterion_id]
        if not criterion.min_score <= item.score <= criterion.max_score:
            raise HTTPException(status_code=422, detail=f"Score for {criterion.name} is outside the allowed range")

    evaluation = Evaluation(event_id=event_id, assignment_id=assignment.id, judge_id=assignment.judge_id, submission_id=assignment.submission_id, overall_comment=payload.overall_comment.strip())
    db.add(evaluation)
    db.flush()
    for item in payload.scores:
        db.add(EvaluationScore(evaluation_id=evaluation.id, criterion_id=item.criterion_id, score=item.score))
    assignment.status = AssignmentStatus.COMPLETED
    record_audit(db, event_id=event_id, actor_user_id=user.id, action="EVALUATION_SUBMITTED", entity_type="evaluation", entity_id=str(evaluation.id), payload={"assignment_id": str(assignment.id)})
    db.commit()
    dispatch_event(db, event_id, "evaluation.submitted", {"evaluation_id": str(evaluation.id), "assignment_id": str(assignment.id), "submission_id": str(assignment.submission_id)})
    return {"id": str(evaluation.id), "status": "submitted"}


@router.get("/events/{event_id}/results")
def results(event_id: UUID, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN))):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if user.role != UserRole.ADMIN and event.organizer_id != user.id:
        raise HTTPException(status_code=403, detail="Organizer access required")
    rubric = _load_active_rubric(db, event_id)
    weights = _weights(db, rubric.id)
    rows = []
    for evaluation in db.scalars(select(Evaluation).where(Evaluation.event_id == event_id)).all():
        for score in db.scalars(select(EvaluationScore).where(EvaluationScore.evaluation_id == evaluation.id)).all():
            rows.append({"judge_id": str(evaluation.judge_id), "submission_id": str(evaluation.submission_id), "criterion_id": str(score.criterion_id), "score": score.score})
    normalized = normalize_scores(rows, "robust_zscore")["scores"] if rows else []
    ranking = aggregate_rankings(normalized, weights) if normalized else []
    return {"event_id": str(event_id), "ranking": ranking, "evaluation_count": len({r["judge_id"] + ':' + r["submission_id"] for r in rows})}

@router.get("/events/{event_id}/exports/evaluations.csv")
def export_evaluations_csv(event: Event = Depends(event_manager), db: Session = Depends(get_db), user: User = Depends(current_user)):
    import csv
    import io
    from fastapi.responses import Response
    rows = []
    evaluations = db.scalars(select(Evaluation).where(Evaluation.event_id == event.id)).all()
    for evaluation in evaluations:
        for score in db.scalars(select(EvaluationScore).where(EvaluationScore.evaluation_id == evaluation.id)).all():
            rows.append([evaluation.id, evaluation.judge_id, evaluation.submission_id, score.criterion_id, score.score, evaluation.submitted_at])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["evaluation_id", "judge_id", "submission_id", "criterion_id", "score", "submitted_at"])
    writer.writerows(rows)
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{event.slug}-evaluations.csv"'})

@router.get("/events/{event_id}/judging/progress")
def judging_progress(event_id: UUID, event: Event = Depends(event_manager), db: Session = Depends(get_db), user: User = Depends(current_user)):
    assignments = db.scalars(select(JudgeAssignment).where(JudgeAssignment.event_id == event_id)).all()
    total = len(assignments)
    completed = sum(1 for a in assignments if a.status == AssignmentStatus.COMPLETED)
    by_judge = defaultdict(lambda: {"assigned": 0, "completed": 0})
    for a in assignments:
        key = str(a.judge_id)
        by_judge[key]["assigned"] += 1
        if a.status == AssignmentStatus.COMPLETED:
            by_judge[key]["completed"] += 1
    return {"event_id": str(event_id), "assigned": total, "completed": completed, "remaining": total - completed, "completion_ratio": (completed / total) if total else 0.0, "by_judge": by_judge}
