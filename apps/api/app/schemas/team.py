from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class TeamUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class InviteCreate(BaseModel):
    invited_email: str | None = Field(default=None, max_length=320)
    expires_hours: int = Field(default=48, ge=1, le=720)


class InviteOut(BaseModel):
    token: str
    join_url: str
    expires_at: datetime
    invited_email: str | None = None


class TeamMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    is_owner: bool
    joined_at: datetime


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    name: str
    created_at: datetime
    members: list[TeamMemberOut]
