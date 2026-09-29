from pydantic import BaseModel

from app.models import UserRole


class UserRoleUpdate(BaseModel):
    role: UserRole