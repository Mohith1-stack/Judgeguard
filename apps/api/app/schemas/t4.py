from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ImportMember(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    is_owner: bool = False

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ImportTeam(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    members: list[ImportMember] = Field(default_factory=list, max_length=50)


class ImportTrack(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=120)
    description: str = ""

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        return value.strip().lower()


class ImportPrize(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    amount: float | None = None
    rank: int | None = None


class ImportSubmission(BaseModel):
    team_name: str = Field(min_length=1, max_length=120)
    track_slug: str | None = Field(default=None, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    tagline: str = Field(default="", max_length=240)
    description: str = ""
    repository_url: str | None = Field(default=None, max_length=1000)
    live_url: str | None = Field(default=None, max_length=1000)
    demo_video_url: str | None = Field(default=None, max_length=1000)
    tech_tags: list[str] = Field(default_factory=list, max_length=30)
    custom_answers: dict = Field(default_factory=dict)


class BulkImportRequest(BaseModel):
    format: str = Field(default="judgeguard.event-export", pattern=r"^judgeguard\.event-export$")
    version: int = Field(default=2, ge=2, le=2)
    tracks: list[ImportTrack] = Field(default_factory=list, max_length=500)
    prizes: list[ImportPrize] = Field(default_factory=list, max_length=500)
    teams: list[ImportTeam] = Field(default_factory=list, max_length=5000)
    submissions: list[ImportSubmission] = Field(default_factory=list, max_length=5000)
