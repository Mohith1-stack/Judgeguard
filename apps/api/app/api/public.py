from __future__ import annotations

import hashlib
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.models import Comment, Event, EventStatus, Submission, SubmissionStatus, User, Vote, VoteAccess
from app.schemas.public import CommentIn, VoteIn
from app.security.auth import current_user, optional_user
from app.services.audit import record_audit
from app.services.deadlines import is_voting_open
from app.services.rate_limit import limiter
from app.services.webhooks import dispatch_event

router = APIRouter(tags=["Public"])


def _client_fingerprint(request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    return hashlib.sha256(host.encode("utf-8")).hexdigest()[:24]


def _voter_identity(request: Request, user: User | None) -> tuple[str, str | None]:
    settings = get_settings()
    if user:
        return f"user:{user.id}", None
    cookie = request.cookies.get(settings.public_voter_cookie_name) or secrets.token_urlsafe(32)
    return "anon:" + hashlib.sha256(cookie.encode("utf-8")).hexdigest(), cookie


@router.get("/events/{event_id}/gallery")
def gallery(
    event_id: UUID,
    q: str | None = Query(default=None, max_length=120),
    track_id: UUID | None = None,
    tag: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    submissions = db.scalars(
        select(Submission).where(
            Submission.event_id == event_id,
            Submission.status == SubmissionStatus.SUBMITTED,
        )
    ).all()
    if q:
        needle = q.strip().lower()
        submissions = [
            s for s in submissions
            if needle in s.name.lower() or needle in s.tagline.lower() or needle in s.description.lower()
        ]
    if track_id:
        submissions = [s for s in submissions if s.track_id == track_id]
    if tag:
        normalized_tag = tag.strip().lower()
        submissions = [s for s in submissions if normalized_tag in {x.lower() for x in (s.tech_tags or [])}]

    items = [
        {
            "id": str(s.id),
            "name": s.name,
            "tagline": s.tagline,
            "description": s.description,
            "thumbnail_url": s.thumbnail_url,
            "demo_video_url": s.demo_video_url,
            "repository_url": s.repository_url,
            "live_url": s.live_url,
            "tech_tags": s.tech_tags or [],
            "track_id": str(s.track_id) if s.track_id else None,
        }
        for s in submissions
    ]
    secrets.SystemRandom().shuffle(items)
    return {
        "event_id": str(event_id),
        "randomized": True,
        "items": items,
    }


@router.post("/events/{event_id}/votes", status_code=201)
def cast_vote(
    event_id: UUID,
    payload: VoteIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User | None = Depends(optional_user),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.status != EventStatus.VOTING or not is_voting_open(event):
        raise HTTPException(status_code=409, detail="Voting is not currently open")
    if event.voting_access == VoteAccess.AUTHENTICATED and user is None:
        raise HTTPException(status_code=401, detail="Authentication required to vote")
    if event.voting_access == VoteAccess.EMAIL_GATED and (user is None or not user.email_verified):
        raise HTTPException(status_code=403, detail="A verified email account is required to vote")

    submission = db.get(Submission, payload.submission_id)
    if submission is None or submission.event_id != event_id or submission.status != SubmissionStatus.SUBMITTED:
        raise HTTPException(status_code=404, detail="Submission not found")

    settings = get_settings()
    limiter_key = f"vote:{event_id}:{user.id if user else _client_fingerprint(request)}"
    allowed, retry_after = limiter.consume(
        limiter_key,
        limit=settings.vote_rate_limit,
        window_seconds=settings.vote_rate_window_seconds,
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many voting requests",
            headers={"Retry-After": str(retry_after)},
        )

    key, voter_cookie = _voter_identity(request, user)
    vote = Vote(
        event_id=event_id,
        submission_id=submission.id,
        voter_user_id=user.id if user else None,
        voter_key=key,
    )
    db.add(vote)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A vote has already been recorded for this event")

    record_audit(
        db,
        event_id=event_id,
        actor_user_id=user.id if user else None,
        action="PUBLIC_VOTE_CAST",
        entity_type="vote",
        entity_id=str(vote.id),
        payload={"submission_id": str(submission.id), "client_fingerprint": _client_fingerprint(request)},
    )
    db.commit()
    dispatch_event(db, event_id, "vote.cast", {"vote_id": str(vote.id), "submission_id": str(submission.id)})
    if user is None and voter_cookie is not None:
        response.set_cookie(
            settings.public_voter_cookie_name,
            voter_cookie,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            path="/",
        )
    return {"id": str(vote.id), "status": "recorded"}


@router.get("/events/{event_id}/votes/results")
def vote_results(event_id: UUID, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if not event.voting_results_published:
        raise HTTPException(status_code=403, detail="Voting results are currently hidden")
    rows = db.execute(
        select(Vote.submission_id, func.count(Vote.id))
        .where(Vote.event_id == event_id)
        .group_by(Vote.submission_id)
        .order_by(func.count(Vote.id).desc(), Vote.submission_id.asc())
    ).all()
    return [{"submission_id": str(submission_id), "votes": int(count)} for submission_id, count in rows]


@router.post("/submissions/{submission_id}/comments", status_code=201)
def add_comment(
    submission_id: UUID,
    payload: CommentIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    submission = db.get(Submission, submission_id)
    if submission is None or submission.status != SubmissionStatus.SUBMITTED:
        raise HTTPException(status_code=404, detail="Submission not found")
    settings = get_settings()
    allowed, retry_after = limiter.consume(
        f"comment:{submission_id}:{user.id}",
        limit=settings.comment_rate_limit,
        window_seconds=settings.comment_rate_window_seconds,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many comments", headers={"Retry-After": str(retry_after)})

    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="Comment cannot be empty")
    comment = Comment(submission_id=submission_id, user_id=user.id, body=body)
    db.add(comment)
    db.flush()
    record_audit(
        db,
        event_id=submission.event_id,
        actor_user_id=user.id,
        action="PUBLIC_COMMENT_CREATED",
        entity_type="comment",
        entity_id=str(comment.id),
        payload={"submission_id": str(submission_id)},
    )
    db.commit()
    dispatch_event(db, submission.event_id, "comment.created", {"comment_id": str(comment.id), "submission_id": str(submission_id)})
    db.refresh(comment)
    return {"id": str(comment.id), "body": comment.body, "created_at": comment.created_at}


@router.get("/submissions/{submission_id}/comments")
def list_comments(
    submission_id: UUID,
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    submission = db.get(Submission, submission_id)
    if submission is None or submission.status != SubmissionStatus.SUBMITTED:
        raise HTTPException(status_code=404, detail="Submission not found")
    rows = db.scalars(
        select(Comment)
        .where(Comment.submission_id == submission_id)
        .order_by(Comment.created_at.asc(), Comment.id.asc())
        .limit(limit)
    ).all()
    return [
        {
            "id": str(r.id),
            "body": r.body,
            "user_id": str(r.user_id) if r.user_id else None,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/events/{event_id}/public/results")
def public_results(event_id: UUID, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if not event.voting_results_published:
        raise HTTPException(status_code=403, detail="Results are not published")
    from app.models import AnalyticsRun
    run = db.scalar(
        select(AnalyticsRun)
        .where(AnalyticsRun.event_id == event_id, AnalyticsRun.kind == "INTEGRITY")
        .order_by(AnalyticsRun.created_at.desc())
    )
    if run is None:
        return {"event_id": str(event_id), "ranking": []}
    return {"event_id": str(event_id), "ranking": run.result.get("ranking", [])}
