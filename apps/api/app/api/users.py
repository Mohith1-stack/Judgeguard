from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.auth import UserOut as UserResponse
from app.schemas.users import UserRoleUpdate
from app.security.rbac import require_roles


router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "",
    response_model=list[UserResponse],
)
def list_users(
    _admin: User = Depends(
        require_roles(UserRole.ADMIN)
    ),
    db: Session = Depends(get_db),
) -> list[User]:
    return list(
        db.scalars(
            select(User).order_by(User.created_at.asc())
        ).all()
    )


@router.patch(
    "/{user_id}/role",
    response_model=UserResponse,
)
def update_user_role(
    user_id: UUID,
    payload: UserRoleUpdate,
    _admin: User = Depends(
        require_roles(UserRole.ADMIN)
    ),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    user.role = payload.role

    db.add(user)
    db.commit()
    db.refresh(user)

    return user
