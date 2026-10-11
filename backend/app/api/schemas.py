"""Pydantic v2 API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CityInfo(BaseModel):
    id: str
    name: str
    province: str
    country: str = "CA"
    country_name: str = "Canada"
    province_name: str = ""
    center: tuple[float, float]
    default_zoom: float
    bounds: tuple[float, float, float, float]


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    resolutions: list[int]
    zones_loaded: dict[int, int]
    cities: list[str] = Field(default_factory=lambda: ["quebec"])


class ZoneScore(BaseModel):
    h3: str
    safety_score: float = Field(ge=0, le=100)
    calmness_score: float = Field(ge=0, le=100)
    family_score: float = Field(default=50.0, ge=0, le=100)


class ZoneDetail(ZoneScore):
    resolution: int
    cluster: int
    profile: str
    counts: dict[str, int]
    centroid: tuple[float, float]  # (lat, lng)
    city: str = "quebec"
    live_active: bool = False
    live_poi_samples: list[dict[str, str]] = Field(default_factory=list)
    live_total_elements: int = 0


class StatsResponse(BaseModel):
    resolution: int
    zone_count: int
    safety_mean: float
    safety_p10: float
    safety_p90: float
    calmness_mean: float
    calmness_p10: float
    calmness_p90: float
    family_mean: float = 50.0
    family_p10: float = 50.0
    family_p90: float = 50.0
    profiles: dict[str, int]
    city: str = "quebec"


class SimulationRequest(BaseModel):
    resolution: int = Field(default=8, description="H3 resolution (8 or 9)")
    city: str = Field(default="quebec", description="Target city id")
    safety_weights: dict[str, float] = Field(default_factory=dict)
    calmness_weights: dict[str, float] = Field(default_factory=dict)
    family_weights: dict[str, float] = Field(default_factory=dict)


class SimulationResponse(BaseModel):
    resolution: int
    city: str = "quebec"
    applied_safety_weights: dict[str, float]
    applied_calmness_weights: dict[str, float]
    applied_family_weights: dict[str, float] = Field(default_factory=dict)
    zones: list[ZoneScore]
