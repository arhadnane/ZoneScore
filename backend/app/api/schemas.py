"""Pydantic v2 API schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    resolutions: list[int]
    zones_loaded: dict[int, int]


class ZoneScore(BaseModel):
    h3: str
    safety_score: float = Field(ge=0, le=100)
    calmness_score: float = Field(ge=0, le=100)


class ZoneDetail(ZoneScore):
    resolution: int
    cluster: int
    profile: str
    counts: dict[str, int]
    centroid: tuple[float, float]  # (lat, lng)


class StatsResponse(BaseModel):
    resolution: int
    zone_count: int
    safety_mean: float
    safety_p10: float
    safety_p90: float
    calmness_mean: float
    calmness_p10: float
    calmness_p90: float
    profiles: dict[str, int]


class SimulationRequest(BaseModel):
    resolution: int = Field(default=8, description="H3 resolution (8 or 9)")
    safety_weights: dict[str, float] = Field(default_factory=dict)
    calmness_weights: dict[str, float] = Field(default_factory=dict)


class SimulationResponse(BaseModel):
    resolution: int
    applied_safety_weights: dict[str, float]
    applied_calmness_weights: dict[str, float]
    zones: list[ZoneScore]
