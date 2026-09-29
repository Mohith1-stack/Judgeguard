from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models import EventStatus, VoteAccess
from app.schemas.event import EventCreate, EventUpdate, validate_schedule_values


def dt(hour: int) -> datetime:
    return datetime(2026, 9, 28, hour, 0, tzinfo=timezone.utc)


def test_valid_event_schedule() -> None:
    event = EventCreate(
        name="Example Event",
        slug="example-event",
        registration_opens_at=dt(9),
        registration_closes_at=dt(10),
        submission_opens_at=dt(10),
        submission_deadline=dt(12),
        judging_opens_at=dt(12),
        judging_deadline=dt(14),
        voting_opens_at=dt(14),
        voting_deadline=dt(16),
        voting_access=VoteAccess.AUTHENTICATED,
    )
    assert event.slug == "example-event"


def test_invalid_phase_pair() -> None:
    with pytest.raises(ValidationError):
        EventCreate(
            name="Example",
            slug="example",
            registration_opens_at=dt(9),
        )


def test_invalid_chronology() -> None:
    with pytest.raises(ValueError):
        validate_schedule_values(
            {
                "registration_opens_at": dt(10),
                "registration_closes_at": dt(9),
                "submission_opens_at": None,
                "submission_deadline": None,
                "judging_opens_at": None,
                "judging_deadline": None,
                "voting_opens_at": None,
                "voting_deadline": None,
            }
        )


def test_partial_update_accepts_metadata_only() -> None:
    update = EventUpdate(name="Updated", status=EventStatus.DRAFT)
    assert update.name == "Updated"
    assert update.status == EventStatus.DRAFT
