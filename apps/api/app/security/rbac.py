from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.models import User, UserRole
from app.security.auth import current_user as get_current_user


def require_roles(*allowed_roles: UserRole) -> Callable:
    """
    Create a FastAPI dependency that allows access only to users
    whose role is explicitly present in allowed_roles.

    Authorization is evaluated on the backend for every request.
    """

    if not allowed_roles:
        raise ValueError("At least one allowed role must be provided.")

    allowed = frozenset(allowed_roles)

    def dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not current_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive.",
            )

        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )

        return current_user

    return dependency