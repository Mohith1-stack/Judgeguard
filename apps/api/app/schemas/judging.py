from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JudgeInviteCreate(BaseModel):
    invited_email: str = Field(min_length=3, max_length=320)
    expires_hours: int = Field(default=72, ge=1, le=720)
    capacity: int = Field(default=10, ge=1, le=500)
    expertise: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("invited_email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise ValueError("Email cannot be empty")
        return value

    @field_validator("expertise")
    @classmethod
    def normalize_expertise(cls, value: list[str]) -> list[str]:
        normalized = []
        seen: set[str] = set()
        for item in value:
            cleaned = item.strip().lower()
            if cleaned and cleaned not in seen:
                normalized.append(cleaned)
                seen.add(cleaned)
        return normalized


class JudgeProfileCreate(BaseModel):
    user_id: UUID
    capacity: int = Field(default=10, ge=1, le=500)
    expertise: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("expertise")
    @classmethod
    def normalize_expertise(cls, value: list[str]) -> list[str]:
        normalized = []
        seen: set[str] = set()
        for item in value:
            cleaned = item.strip().lower()
            if cleaned and cleaned not in seen:
                normalized.append(cleaned)
                seen.add(cleaned)
        return normalized


class JudgeProfileUpdate(BaseModel):
    capacity: int | None = Field(default=None, ge=1, le=500)
    expertise: list[str] | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("expertise")
    @classmethod
    def normalize_expertise(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = []
        seen: set[str] = set()
        for item in value:
            cleaned = item.strip().lower()
            if cleaned and cleaned not in seen:
                normalized.append(cleaned)
                seen.add(cleaned)
        return normalized

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class ConflictCreate(BaseModel):
    judge_id: UUID
    team_id: UUID
    reason: str = Field(min_length=1, max_length=300)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Conflict reason cannot be empty")
        return value


class ConflictOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    judge_id: UUID
    team_id: UUID
    reason: str


class JudgeInviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    invited_email: str
    expires_at: datetime
    capacity: int
    expertise: list[str]
    accepted_at: datetime | None


class JudgeProfileOut(BaseModel):
    id: UUID
    event_id: UUID
    user_id: UUID
    email: str
    display_name: str
    role: str
    capacity: int
    expertise: list[str]
    notes: str


class RubricCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Rubric name cannot be empty")
        return value


class RubricUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=160)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Rubric name cannot be empty")
        return value


class CriterionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    weight: float = Field(gt=0, le=1)
    min_score: float = 1
    max_score: float = 5
    sort_order: int = 0

    @field_validator("name", "description")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("max_score")
    @classmethod
    def validate_max_score(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("max_score must be positive")
        return value


class CriterionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    weight: float | None = Field(default=None, gt=0, le=1)
    min_score: float | None = None
    max_score: float | None = None
    sort_order: int | None = None

    @field_validator("name", "description")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class CriterionOut(BaseModel):
    id: UUID
    rubric_id: UUID
    name: str
    description: str
    weight: float
    min_score: float
    max_score: float
    sort_order: int


class RubricOut(BaseModel):
    id: UUID
    event_id: UUID
    name: str
    version: int
    is_active: bool
    criteria: list[CriterionOut]


class RubricValidationOut(BaseModel):
    valid: bool
    errors: list[str]
    warnings: list[str]
    weight_sum: float
    criterion_count: int


class AssignmentRequest(BaseModel):
    reviews_per_submission: int = Field(default=3, ge=1, le=20)
    seed: int | None = Field(default=None, ge=0, le=(2**63) - 1)
    optimization_restarts: int = Field(default=24, ge=1, le=200)




class EvaluationScoreIn(BaseModel):
    criterion_id: UUID
    score: float


class EvaluationIn(BaseModel):
    scores: list[EvaluationScoreIn] = Field(min_length=1)
    overall_comment: str = ""


class IntegrityRunRequest(BaseModel):
    normalization_method: str = "robust_zscore"
    bootstrap_iterations: int = Field(default=500, ge=100, le=5000)
    attack_max_coalition: int = Field(default=3, ge=1, le=4)
    sensitivity_delta: float = Field(default=0.05, gt=0, lt=0.25)


class ReviewDecision(BaseModel):
    accept: bool


class JudgeAssignmentOut(BaseModel):
    id: UUID
    judge_id: UUID
    submission_id: UUID
    queue_position: int
    status: str


class AssignmentDiagnostics(BaseModel):
    total_assignments: int
    judge_count: int
    submission_count: int
    reviews_per_submission: int
    mean_judge_load: float
    max_judge_load: int
    min_judge_load: int
    load_deviation: float
    max_pair_overlap: int
    mean_pair_overlap: float
    max_track_concentration: float
    order_edge_risk: float
    structural_risk: float
    structural_integrity: float
    max_load_excess: float


class AssignmentPreviewItem(BaseModel):
    judge_id: UUID
    submission_id: UUID
    queue_position: int


class AssignmentPreviewOut(BaseModel):
    seed: int
    optimization_restarts: int
    review_count: int
    judge_load: dict[str, int]
    diagnostics: AssignmentDiagnostics
    assignments: list[AssignmentPreviewItem]

class WebhookCreate(BaseModel):
    url: str = Field(min_length=8, max_length=1000)
    secret: str = Field(min_length=16, max_length=512)
