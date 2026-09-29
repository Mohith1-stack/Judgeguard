from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Event, EventPrize, EventStatus, EventTrack, Submission, User, UserRole
from app.schemas.event import EventCreate, EventOut, EventUpdate
from app.security.auth import current_user
from app.security.rbac import require_roles
from app.security.authorization import event_manager
from app.services.audit import record_audit
from app.services.webhooks import dispatch_event

router = APIRouter(tags=["Events"])


@router.get("/events", response_model=list[EventOut])
def list_events(db: Session = Depends(get_db)) -> list[Event]:
    return list(db.scalars(select(Event).order_by(Event.created_at.desc())).all())


@router.post("/events", response_model=EventOut, status_code=201)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN)),
) -> Event:
    if db.scalar(select(Event).where(Event.slug == payload.slug)) is not None:
        raise HTTPException(status_code=409, detail="Event slug already exists")
    event = Event(organizer_id=user.id, **payload.model_dump())
    db.add(event)
    db.flush()
    record_audit(db, event_id=event.id, actor_user_id=user.id, action="EVENT_CREATED", entity_type="event", entity_id=str(event.id))
    db.commit()
    db.refresh(event)
    dispatch_event(db, event.id, "event.created", {"event_id": str(event.id), "name": event.name})
    return event


@router.get("/events/{event_id}", response_model=EventOut)
def get_event(event_id: UUID, db: Session = Depends(get_db)) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.patch("/events/{event_id}", response_model=EventOut)
def update_event(
    event_id: UUID,
    payload: EventUpdate,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Event:
    updates = payload.model_dump(exclude_unset=True)
    next_status = updates.get("status", event.status)
    next_results_published = updates.get("voting_results_published", event.voting_results_published)

    if next_results_published and not event.voting_results_published:
        deadline = updates.get("voting_deadline", event.voting_deadline)
        deadline_passed = deadline is not None and datetime.now(timezone.utc) >= deadline
        lifecycle_reached = next_status in {EventStatus.RESULTS_PUBLISHED, EventStatus.ARCHIVED}
        if not deadline_passed and not lifecycle_reached:
            raise HTTPException(status_code=409, detail="Voting results cannot be published while voting is active")

    if next_status == EventStatus.RESULTS_PUBLISHED and not next_results_published:
        deadline = updates.get("voting_deadline", event.voting_deadline)
        if deadline is not None and datetime.now(timezone.utc) < deadline:
            raise HTTPException(status_code=409, detail="Results cannot be published before the voting deadline")

    for key, value in updates.items():
        setattr(event, key, value)
    record_audit(
        db,
        event_id=event.id,
        actor_user_id=user.id,
        action="EVENT_UPDATED",
        entity_type="event",
        entity_id=str(event.id),
        payload=payload.model_dump(exclude_unset=True, mode="json"),
    )
    db.commit()
    db.refresh(event)
    dispatch_event(db, event.id, "event.updated", {"event_id": str(event.id), "fields": sorted(updates.keys())})
    return event


@router.post("/events/{event_id}/tracks", response_model=dict, status_code=201)
def add_track(event: Event = Depends(event_manager), db: Session = Depends(get_db), user: User = Depends(current_user), name: str = "", slug: str = "", description: str = ""):
    name, slug = name.strip(), slug.strip().lower()
    if not name or not slug:
        raise HTTPException(status_code=422, detail="name and slug are required")
    if db.scalar(select(EventTrack).where(EventTrack.event_id == event.id, EventTrack.slug == slug)):
        raise HTTPException(status_code=409, detail="Track slug already exists")
    track = EventTrack(event_id=event.id, name=name, slug=slug, description=description.strip())
    db.add(track)
    record_audit(db, event_id=event.id, actor_user_id=user.id, action="TRACK_CREATED", entity_type="event_track", entity_id=str(track.id), payload={"slug": slug})
    db.commit()
    db.refresh(track)
    return {"id": str(track.id), "name": track.name, "slug": track.slug}


@router.post("/events/{event_id}/prizes", response_model=dict, status_code=201)
def add_prize(event: Event = Depends(event_manager), db: Session = Depends(get_db), user: User = Depends(current_user), name: str = "", description: str = "", amount: float | None = None, rank: int | None = None):
    if not name.strip():
        raise HTTPException(status_code=422, detail="name is required")
    prize = EventPrize(event_id=event.id, name=name.strip(), description=description.strip(), amount=amount, rank=rank)
    db.add(prize)
    record_audit(db, event_id=event.id, actor_user_id=user.id, action="PRIZE_CREATED", entity_type="event_prize", entity_id=str(prize.id), payload={"name": prize.name, "rank": rank})
    db.commit()
    db.refresh(prize)
    return {"id": str(prize.id), "name": prize.name, "amount": prize.amount, "rank": prize.rank}


@router.get("/events/{event_id}/exports/submissions.csv")
def export_submissions_csv(event_id: UUID, event: Event = Depends(event_manager), db: Session = Depends(get_db), user: User = Depends(current_user)):
    import csv
    import io

    rows = db.scalars(select(Submission).where(Submission.event_id == event_id)).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "team_id", "track_id", "name", "tagline", "status", "submitted_at", "repository_url", "live_url"])
    for s in rows:
        writer.writerow([s.id, s.team_id, s.track_id, s.name, s.tagline, s.status.value, s.submitted_at, s.repository_url, s.live_url])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{event.slug}-submissions.csv"'},
    )
