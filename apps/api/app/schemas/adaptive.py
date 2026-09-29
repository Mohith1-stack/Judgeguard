from pydantic import BaseModel, Field


class AdaptiveReviewRequest(BaseModel):
    target_rank_limit: int = Field(default=5, ge=1, le=10)
    max_candidates: int = Field(default=20, ge=1, le=100)
    minimum_priority: float = Field(default=0.0, ge=0.0, le=1.0)


class AdaptiveRecalculateRequest(BaseModel):
    bootstrap_iterations: int = Field(default=500, ge=100, le=5000)
    attack_max_coalition: int = Field(default=3, ge=1, le=4)
    sensitivity_delta: float = Field(default=0.05, gt=0.0, lt=0.25)
