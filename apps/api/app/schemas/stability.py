from pydantic import BaseModel, Field


class StabilityAnalysisRequest(BaseModel):
    normalization_method: str = Field(default="robust_zscore")
    min_observations: int = Field(default=3, ge=2, le=100)
    clip: bool = True
    bootstrap_iterations: int = Field(default=1000, ge=100, le=5000)
    seed: int | None = Field(default=0, ge=0, le=2**63 - 1)
    top_k: int = Field(default=3, ge=1, le=10)
    pairwise_top_n: int = Field(default=5, ge=2, le=10)
    sensitivity_delta: float = Field(default=0.05, gt=0, lt=0.5)
    sensitivity_steps: int = Field(default=4, ge=1, le=10)
