from pydantic import BaseModel, Field


class NormalizationRunRequest(BaseModel):
    normalization_method: str = Field(default="robust_zscore")
    min_observations: int = Field(default=3, ge=2, le=100)
    clip: bool = True


class CalibrationAnalysisRequest(BaseModel):
    min_observations: int = Field(default=3, ge=2, le=100)


class DriftAnalysisRequest(BaseModel):
    min_observations: int = Field(default=3, ge=2, le=100)
