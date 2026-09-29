from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Event, EventStatus, Rubric, RubricCriterion


@dataclass(frozen=True)
class RubricValidation:
    valid: bool
    errors: list[str]
    warnings: list[str]
    weight_sum: float
    criterion_count: int


def get_active_rubric(db: Session, event_id: UUID) -> Rubric | None:
    return db.scalar(
        select(Rubric)
        .where(
            Rubric.event_id == event_id,
            Rubric.is_active.is_(True),
        )
        .order_by(Rubric.version.desc())
    )


def validate_rubric(db: Session, rubric: Rubric) -> RubricValidation:
    criteria = list(
        db.scalars(
            select(RubricCriterion)
            .where(RubricCriterion.rubric_id == rubric.id)
            .order_by(RubricCriterion.sort_order, RubricCriterion.id)
        ).all()
    )

    errors: list[str] = []
    warnings: list[str] = []

    if not criteria:
        errors.append("At least one criterion is required.")

    names: set[str] = set()
    weight_sum = 0.0

    for criterion in criteria:
        normalized_name = criterion.name.strip().casefold()
        if normalized_name in names:
            errors.append(f"Duplicate criterion name: {criterion.name}")
        names.add(normalized_name)

        if criterion.weight <= 0:
            errors.append(f"Criterion '{criterion.name}' must have a positive weight.")

        if criterion.min_score >= criterion.max_score:
            errors.append(
                f"Criterion '{criterion.name}' must have min_score lower than max_score."
            )

        weight_sum += criterion.weight

    rounded_weight_sum = round(weight_sum, 10)
    if abs(rounded_weight_sum - 1.0) > 0.000001:
        errors.append(
            f"Criterion weights must sum to 1.0; current sum is {rounded_weight_sum:.6f}."
        )

    if len(criteria) == 1:
        warnings.append("A single criterion provides no cross-criterion weighting.")

    if any(c.weight < 0.05 for c in criteria):
        warnings.append("One or more criteria have weights below 0.05.")

    return RubricValidation(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        weight_sum=rounded_weight_sum,
        criterion_count=len(criteria),
    )


def ensure_rubric_configurable(event: Event, rubric: Rubric) -> None:
    if event.status in {
        EventStatus.JUDGING,
        EventStatus.VOTING,
        EventStatus.RESULTS_PUBLISHED,
        EventStatus.ARCHIVED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rubrics are frozen once judging begins.",
        )

    if rubric.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Active rubrics are immutable. Create a new rubric version to make changes.",
        )
