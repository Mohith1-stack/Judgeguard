from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Team, TeamInvite, TeamMember, User
from app.schemas.team import InviteCreate, InviteOut, TeamCreate, TeamOut
from app.security.auth import current_user
from app.services.audit import record_audit
from app.services.deadlines import now_utc
from app.services.webhooks import dispatch_event

router = APIRouter(tags=["Teams"])


def _team_out(team: Team) -> TeamOut:
    return TeamOut(
        id=team.id,
        event_id=team.event_id,
        name=team.name,
        created_at=team.created_at,
        members=team.members,
    )


def _is_member(db: Session, team_id: UUID, user_id: UUID) -> bool:
    return db.scalar(select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user_id)) is not None


def _is_owner(db: Session, team_id: UUID, user_id: UUID) -> bool:
    member = db.scalar(select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user_id))
    return bool(member and member.is_owner)


@router.post("/events/{event_id}/teams", response_model=TeamOut, status_code=201)
def create_team(event_id: UUID, payload: TeamCreate, db: Session = Depends(get_db), user: User = Depends(current_user)) -> TeamOut:
    from app.models import Event
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    existing = db.scalar(select(Team).where(Team.event_id == event_id, Team.name == payload.name.strip()))
    if existing:
        raise HTTPException(status_code=409, detail="Team name already exists in this event")

    team = Team(event_id=event_id, name=payload.name.strip())
    db.add(team)
    db.flush()
    db.add(TeamMember(team_id=team.id, user_id=user.id, is_owner=True))
    record_audit(db, event_id=event.id, actor_user_id=user.id, action="TEAM_CREATED", entity_type="team", entity_id=str(team.id))
    db.commit()
    dispatch_event(db, event.id, "team.created", {"team_id": str(team.id), "name": team.name})
    team = db.scalar(select(Team).options(selectinload(Team.members)).where(Team.id == team.id))
    return _team_out(team)


@router.get("/events/{event_id}/teams", response_model=list[TeamOut])
def list_teams(event_id: UUID, db: Session = Depends(get_db)) -> list[TeamOut]:
    teams = db.scalars(select(Team).options(selectinload(Team.members)).where(Team.event_id == event_id).order_by(Team.created_at)).all()
    return [_team_out(team) for team in teams]


@router.post("/teams/{team_id}/invites", response_model=InviteOut, status_code=201)
def create_invite(team_id: UUID, payload: InviteCreate, db: Session = Depends(get_db), user: User = Depends(current_user)) -> InviteOut:
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    if not _is_owner(db, team_id, user.id):
        raise HTTPException(status_code=403, detail="Team owner required")

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=payload.expires_hours)
    db.add(TeamInvite(team_id=team_id, token_hash=token_hash, invited_email=(payload.invited_email or '').strip().lower() or None, expires_at=expires_at))
    db.commit()
    dispatch_event(db, team.event_id, "team.invite.created", {"team_id": str(team.id), "invited_email": (payload.invited_email or "").strip().lower() or None, "expires_at": expires_at.isoformat()})
    return InviteOut(token=token, expires_at=expires_at)


@router.post("/teams/join/{token}", response_model=TeamOut)
def join_team(token: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> TeamOut:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    invite = db.scalar(select(TeamInvite).where(TeamInvite.token_hash == token_hash))
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.used_at is not None or invite.expires_at <= now_utc():
        raise HTTPException(status_code=410, detail="Invite expired or already used")
    if invite.invited_email and invite.invited_email != user.email.lower():
        raise HTTPException(status_code=403, detail="Invite was issued for another email")
    team_event_id = invite.team.event_id
    if _is_member(db, invite.team_id, user.id):
        invite.used_at = now_utc()
        db.commit()
    else:
        db.add(TeamMember(team_id=invite.team_id, user_id=user.id, is_owner=False))
        invite.used_at = now_utc()
        db.commit()
    dispatch_event(db, team_event_id, "team.member.joined", {"team_id": str(invite.team_id), "user_id": str(user.id)})

    team = db.scalar(select(Team).options(selectinload(Team.members)).where(Team.id == invite.team_id))
    return _team_out(team)

@router.get("/events/{event_id}/teams/mine", response_model=list[TeamOut])
def my_teams(event_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)) -> list[TeamOut]:
    teams = db.scalars(
        select(Team)
        .join(TeamMember)
        .where(Team.event_id == event_id, TeamMember.user_id == user.id)
        .options(selectinload(Team.members))
        .order_by(Team.created_at)
    ).all()
    return [_team_out(team) for team in teams]
