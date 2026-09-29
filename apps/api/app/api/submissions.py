from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Event, Submission, SubmissionStatus, SubmissionVersion, TeamMember, User
from app.schemas.submission import SubmissionOut, SubmissionUpsert
from app.security.auth import current_user
from app.services.audit import record_audit
from app.services.deadlines import is_submission_open, now_utc
from app.services.webhooks import dispatch_event

router = APIRouter(tags=["Submissions"])


def _is_team_member(db: Session, team_id: UUID, user_id: UUID) -> bool:
    return db.scalar(select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user_id)) is not None


def _out(s: Submission) -> SubmissionOut:
    return SubmissionOut(
        id=s.id, event_id=s.event_id, team_id=s.team_id, track_id=s.track_id,
        name=s.name, tagline=s.tagline, description=s.description,
        thumbnail_url=s.thumbnail_url, demo_video_url=s.demo_video_url,
        repository_url=s.repository_url, live_url=s.live_url,
        tech_tags=s.tech_tags or [], custom_answers=s.custom_answers or {},
        status=s.status, submitted_at=s.submitted_at,
        created_at=s.created_at, updated_at=s.updated_at,
    )


@router.post("/teams/{team_id}/submissions", response_model=SubmissionOut, status_code=201)
def create_submission(team_id: UUID, payload: SubmissionUpsert, db: Session = Depends(get_db), user: User = Depends(current_user)) -> SubmissionOut:
    from app.models import Team
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    if not _is_team_member(db, team_id, user.id):
        raise HTTPException(status_code=403, detail="Team membership required")
    event = db.get(Event, team.event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if not is_submission_open(event):
        raise HTTPException(status_code=409, detail="Submission window is closed")
    if db.scalar(select(Submission).where(Submission.team_id == team_id, Submission.event_id == event.id)):
        raise HTTPException(status_code=409, detail="A submission already exists for this team")

    data = payload.model_dump(mode="json")
    submission = Submission(event_id=event.id, team_id=team_id, **data)
    db.add(submission)
    db.flush()
    db.add(SubmissionVersion(submission_id=submission.id, version_number=1, payload=data, created_by=user.id))
    record_audit(db, event_id=event.id, actor_user_id=user.id, action="SUBMISSION_CREATED", entity_type="submission", entity_id=str(submission.id))
    db.commit()
    dispatch_event(db, event.id, "submission.created", {"submission_id": str(submission.id), "team_id": str(team_id)})
    db.refresh(submission)
    return _out(submission)


@router.patch("/submissions/{submission_id}", response_model=SubmissionOut)
def update_submission(submission_id: UUID, payload: SubmissionUpsert, db: Session = Depends(get_db), user: User = Depends(current_user)) -> SubmissionOut:
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if not _is_team_member(db, submission.team_id, user.id):
        raise HTTPException(status_code=403, detail="Team membership required")
    event = db.get(Event, submission.event_id)
    if not event or not is_submission_open(event):
        raise HTTPException(status_code=409, detail="Submission window is closed")
    if submission.status == SubmissionStatus.LOCKED:
        raise HTTPException(status_code=409, detail="Submission is locked")

    data = payload.model_dump(mode="json")
    for key, value in data.items():
        setattr(submission, key, value)
    current_version = db.scalar(select(SubmissionVersion.version_number).where(SubmissionVersion.submission_id == submission.id).order_by(SubmissionVersion.version_number.desc()).limit(1)) or 0
    db.add(SubmissionVersion(submission_id=submission.id, version_number=int(current_version) + 1, payload=data, created_by=user.id))
    record_audit(db, event_id=event.id, actor_user_id=user.id, action="SUBMISSION_UPDATED", entity_type="submission", entity_id=str(submission.id), payload={"version": int(current_version) + 1})
    db.commit()
    dispatch_event(db, event.id, "submission.updated", {"submission_id": str(submission.id), "version": int(current_version) + 1})
    db.refresh(submission)
    return _out(submission)


@router.post("/submissions/{submission_id}/submit", response_model=SubmissionOut)
def submit_submission(submission_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)) -> SubmissionOut:
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if not _is_team_member(db, submission.team_id, user.id):
        raise HTTPException(status_code=403, detail="Team membership required")
    event = db.get(Event, submission.event_id)
    if not event or not is_submission_open(event):
        raise HTTPException(status_code=409, detail="Submission deadline has passed")
    submission.status = SubmissionStatus.SUBMITTED
    submission.submitted_at = now_utc()
    record_audit(db, event_id=event.id, actor_user_id=user.id, action="SUBMISSION_SUBMITTED", entity_type="submission", entity_id=str(submission.id))
    db.commit()
    dispatch_event(db, event.id, "submission.submitted", {"submission_id": str(submission.id), "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None})
    db.refresh(submission)
    return _out(submission)


@router.get("/events/{event_id}/submissions", response_model=list[SubmissionOut])
def list_submissions(event_id: UUID, db: Session = Depends(get_db)) -> list[SubmissionOut]:
    rows = db.scalars(select(Submission).where(Submission.event_id == event_id, Submission.status != SubmissionStatus.DRAFT).order_by(Submission.submitted_at.desc().nullslast())).all()
    return [_out(x) for x in rows]


@router.get("/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: UUID, db: Session = Depends(get_db)) -> SubmissionOut:
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return _out(submission)
