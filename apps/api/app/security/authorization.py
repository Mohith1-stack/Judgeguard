from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Event, User, UserRole
from app.security.auth import current_user


def event_manager(
    event_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if user.role == UserRole.ADMIN:
        return event
    if user.role != UserRole.ORGANIZER or event.organizer_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organizer access required")
    return event
