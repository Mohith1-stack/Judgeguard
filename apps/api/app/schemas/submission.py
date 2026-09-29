from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.models import SubmissionQuestionType, SubmissionStatus


class SubmissionQuestionCreate(BaseModel):
    key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:[_-][a-z0-9]+)*$")
    label: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=5000)
    question_type: SubmissionQuestionType
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=50)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("key", "label", "description", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("options")
    @classmethod
    def clean_options(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            normalized = item.strip()
            if not normalized:
                raise ValueError("Options cannot contain empty values")
            lowered = normalized.casefold()
            if lowered in seen:
                raise ValueError("Options must be unique")
            seen.add(lowered)
            cleaned.append(normalized)
        return cleaned

    @model_validator(mode="after")
    def validate_options_for_type(self) -> "SubmissionQuestionCreate":
        requires_options = self.question_type in {
            SubmissionQuestionType.SINGLE_SELECT,
            SubmissionQuestionType.MULTI_SELECT,
        }
        if requires_options and not self.options:
            raise ValueError("Selection questions require at least one option")
        if not requires_options and self.options:
            raise ValueError("Options are only allowed for selection questions")
        return self


class SubmissionQuestionUpdate(BaseModel):
    key: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:[_-][a-z0-9]+)*$")
    label: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=5000)
    question_type: SubmissionQuestionType | None = None
    required: bool | None = None
    options: list[str] | None = Field(default=None, max_length=50)
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

    @field_validator("key", "label", "description")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("options")
    @classmethod
    def clean_options(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            normalized = item.strip()
            if not normalized:
                raise ValueError("Options cannot contain empty values")
            lowered = normalized.casefold()
            if lowered in seen:
                raise ValueError("Options must be unique")
            seen.add(lowered)
            cleaned.append(normalized)
        return cleaned


class SubmissionQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    key: str
    label: str
    description: str
    question_type: SubmissionQuestionType
    required: bool
    options: list[str]
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SubmissionUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    tagline: str = Field(default="", max_length=240)
    description: str = Field(default="", max_length=20000)
    thumbnail_url: HttpUrl | None = None
    demo_video_url: HttpUrl | None = None
    repository_url: HttpUrl | None = None
    live_url: HttpUrl | None = None
    tech_tags: list[str] = Field(default_factory=list, max_length=30)
    custom_answers: dict = Field(default_factory=dict)
    track_id: UUID | None = None

    @field_validator("name", "tagline", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("tech_tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        cleaned = []
        seen = set()
        for item in value:
            tag = item.strip().lower()
            if tag and tag not in seen:
                seen.add(tag)
                cleaned.append(tag)
        return cleaned


class SubmissionMediaCreate(BaseModel):
    url: HttpUrl
    caption: str = Field(default="", max_length=240)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("caption")
    @classmethod
    def strip_caption(cls, value: str) -> str:
        return value.strip()


class SubmissionMediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    submission_id: UUID
    url: str
    caption: str
    sort_order: int


class SubmissionVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    submission_id: UUID
    version_number: int
    created_by: UUID
    created_at: datetime


class SubmissionOut(BaseModel):
    id: UUID
    event_id: UUID
    team_id: UUID
    track_id: UUID | None
    name: str
    tagline: str
    description: str
    thumbnail_url: str | None
    demo_video_url: str | None
    repository_url: str | None
    live_url: str | None
    tech_tags: list[str]
    custom_answers: dict
    status: SubmissionStatus
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    current_version: int
    media: list[SubmissionMediaOut]
