from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent


def record_audit(
    db: Session,
    *,
    event_id: UUID | None,
    actor_user_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: dict | None = None,
) -> None:
    db.add(
        AuditEvent(
            event_id=event_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload or {},
        )
    )


def list_audit_events(
    db: Session,
    *,
    event_id: UUID,
    limit: int = 100,
    action: str | None = None,
) -> list[AuditEvent]:
    stmt = select(AuditEvent).where(AuditEvent.event_id == event_id)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    return list(db.scalars(stmt.order_by(AuditEvent.created_at.desc()).limit(limit)).all())
