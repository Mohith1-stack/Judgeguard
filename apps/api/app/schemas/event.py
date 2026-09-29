from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import EventStatus, VoteAccess


TIMELINE_FIELDS = (
    "registration_opens_at",
    "registration_closes_at",
    "submission_opens_at",
    "submission_deadline",
    "judging_opens_at",
    "judging_deadline",
    "voting_opens_at",
    "voting_deadline",
)


def normalize_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_schedule_values(values: dict[str, datetime | None]) -> None:
    phase_pairs = (
        ("registration_opens_at", "registration_closes_at", "registration"),
        ("submission_opens_at", "submission_deadline", "submission"),
        ("judging_opens_at", "judging_deadline", "judging"),
        ("voting_opens_at", "voting_deadline", "voting"),
    )

    present: list[tuple[str, datetime]] = []
    for open_field, close_field, phase in phase_pairs:
        opened = values.get(open_field)
        closed = values.get(close_field)

        if (opened is None) != (closed is None):
            raise ValueError(
                f"Both {open_field} and {close_field} are required "
                f"when configuring {phase} dates."
            )

        if opened is not None and closed is not None and opened >= closed:
            raise ValueError(f"{open_field} must be earlier than {close_field}.")

    for field in TIMELINE_FIELDS:
        value = values.get(field)
        if value is not None:
            present.append((field, value))

    for (previous_name, previous), (current_name, current) in zip(present, present[1:]):
        if previous > current:
            raise ValueError(
                "Event dates must be chronological: "
                f"{previous_name} must not be later than {current_name}."
            )


class EventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    description: str = Field(default="", max_length=10000)
    registration_opens_at: datetime | None = None
    registration_closes_at: datetime | None = None
    submission_opens_at: datetime | None = None
    submission_deadline: datetime | None = None
    judging_opens_at: datetime | None = None
    judging_deadline: datetime | None = None
    voting_opens_at: datetime | None = None
    voting_deadline: datetime | None = None
    voting_access: VoteAccess = VoteAccess.AUTHENTICATED

    @field_validator("name", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator(*TIMELINE_FIELDS, mode="before")
    @classmethod
    def normalize_dates(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime(value)

    @model_validator(mode="after")
    def validate_schedule(self) -> "EventCreate":
        validate_schedule_values(self.model_dump())
        return self


class EventUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    status: EventStatus | None = None
    registration_opens_at: datetime | None = None
    registration_closes_at: datetime | None = None
    submission_opens_at: datetime | None = None
    submission_deadline: datetime | None = None
    judging_opens_at: datetime | None = None
    judging_deadline: datetime | None = None
    voting_opens_at: datetime | None = None
    voting_deadline: datetime | None = None
    voting_access: VoteAccess | None = None
    voting_results_published: bool | None = None

    @field_validator("name", "description")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator(*TIMELINE_FIELDS, mode="before")
    @classmethod
    def normalize_dates(cls, value: datetime | str | None) -> datetime | None:
        return normalize_datetime(value)


class EventStatusUpdate(BaseModel):
    status: EventStatus


class TrackCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    description: str = Field(default="", max_length=5000)

    @field_validator("name", "slug", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class TrackUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("name", "slug", "description")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class TrackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    name: str
    slug: str
    description: str


class PrizeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=5000)
    amount: float | None = Field(default=None, ge=0)
    rank: int | None = Field(default=None, ge=1)

    @field_validator("name", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class PrizeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    amount: float | None = Field(default=None, ge=0)
    rank: int | None = Field(default=None, ge=1)

    @field_validator("name", "description")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class PrizeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    name: str
    description: str
    amount: float | None
    rank: int | None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organizer_id: UUID
    name: str
    slug: str
    description: str
    status: EventStatus
    voting_access: VoteAccess
    voting_results_published: bool
    registration_opens_at: datetime | None
    registration_closes_at: datetime | None
    submission_opens_at: datetime | None
    submission_deadline: datetime | None
    judging_opens_at: datetime | None
    judging_deadline: datetime | None
    voting_opens_at: datetime | None
    voting_deadline: datetime | None
    created_at: datetime
    updated_at: datetime


class EventDetailOut(EventOut):
    tracks: list[TrackOut]
    prizes: list[PrizeOut]


def validate_event_schedule_from_model(
    event_values: dict[str, datetime | None],
) -> None:
    values = {
        field: normalize_datetime(event_values.get(field))
        for field in TIMELINE_FIELDS
    }
    validate_schedule_values(values)
