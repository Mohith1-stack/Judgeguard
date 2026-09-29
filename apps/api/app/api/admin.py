from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AuditEvent, User, UserRole
from app.security.rbac import require_roles
from app.services.audit import record_audit

router = APIRouter(prefix="/admin", tags=["Administration"])


class RoleUpdate(BaseModel):
    role: UserRole


class EmailVerification(BaseModel):
    verified: bool = True


@router.get("/users")
def list_users(db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ADMIN))):
    users = db.scalars(select(User).order_by(User.created_at)).all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "display_name": u.display_name,
            "role": u.role.value,
            "is_active": u.is_active,
            "email_verified": u.email_verified,
        }
        for u in users
    ]


@router.patch("/users/{user_id}/role")
def update_role(
    user_id: UUID,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.ADMIN)),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role == UserRole.ADMIN and payload.role != UserRole.ADMIN:
        admin_count = db.scalar(select(func.count()).select_from(User).where(User.role == UserRole.ADMIN, User.is_active.is_(True))) or 0
        if admin_count <= 1:
            raise HTTPException(status_code=409, detail="The last active administrator cannot be removed")

    user.role = payload.role
    record_audit(
        db,
        event_id=None,
        actor_user_id=actor.id,
        action="USER_ROLE_CHANGED",
        entity_type="user",
        entity_id=str(user.id),
        payload={"role": payload.role.value},
    )
    db.commit()
    return {"id": str(user.id), "role": user.role.value}


@router.patch("/users/{user_id}/email-verification")
def set_email_verification(
    user_id: UUID,
    payload: EmailVerification,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.ADMIN)),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.email_verified = payload.verified
    record_audit(
        db,
        event_id=None,
        actor_user_id=actor.id,
        action="USER_EMAIL_VERIFICATION_CHANGED",
        entity_type="user",
        entity_id=str(user.id),
        payload={"verified": payload.verified},
    )
    db.commit()
    return {"id": str(user.id), "email_verified": user.email_verified}


@router.get("/audit")
def global_audit(
    limit: int = 100,
    action: str | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.ADMIN)),
):
    limit = min(max(limit, 1), 200)
    stmt = select(AuditEvent)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    rows = db.scalars(stmt.order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": str(r.id),
            "event_id": str(r.event_id) if r.event_id else None,
            "actor_user_id": str(r.actor_user_id) if r.actor_user_id else None,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "payload": r.payload,
            "created_at": r.created_at,
        }
        for r in rows
    ]
