from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def is_submission_open(event) -> bool:
    now = now_utc()
    if event.submission_opens_at and now < event.submission_opens_at:
        return False
    if event.submission_deadline and now > event.submission_deadline:
        return False
    return True


def is_judging_open(event) -> bool:
    now = now_utc()
    if event.judging_opens_at and now < event.judging_opens_at:
        return False
    if event.judging_deadline and now > event.judging_deadline:
        return False
    return True


def is_voting_open(event) -> bool:
    now = now_utc()
    if event.voting_opens_at and now < event.voting_opens_at:
        return False
    if event.voting_deadline and now > event.voting_deadline:
        return False
    return True
