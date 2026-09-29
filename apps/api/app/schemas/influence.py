from pydantic import BaseModel, Field


class InfluenceAnalysisRequest(BaseModel):
    normalization_method: str = Field(default="robust_zscore")
    min_observations: int = Field(default=3, ge=2, le=100)
    clip: bool = True
    max_coalition: int = Field(default=3, ge=1, le=4)
    max_exact_judges: int = Field(default=40, ge=1, le=100)
    max_reported_coalitions: int = Field(default=10, ge=1, le=50)
