"""API routes: zones, scores, statistics and what-if simulation."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import (
    HealthResponse,
    SimulationRequest,
    SimulationResponse,
    StatsResponse,
    ZoneDetail,
    ZoneScore,
)
from app.api.store import get_store
from app.core.config import get_settings
from app.core.constants import FEATURES
from app.models.scoring import CALMNESS_WEIGHTS, SAFETY_WEIGHTS, compute_scores

router = APIRouter(prefix="/api")


def _validate_resolution(resolution: int) -> None:
    if resolution not in get_store().resolutions():
        raise HTTPException(status_code=404, detail=f"No data for resolution {resolution}.")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    s = get_settings()
    store = get_store()
    return HealthResponse(
        status="ok",
        app=s.app_name,
        version=s.version,
        resolutions=store.resolutions(),
        zones_loaded=store.zone_counts(),
    )


@router.get("/zones")
def zones(resolution: int = Query(default=8, ge=0, le=15)) -> dict:
    """GeoJSON FeatureCollection of scored H3 zones."""
    _validate_resolution(resolution)
    return get_store().geojson(resolution)


@router.get("/zones/{cell}", response_model=ZoneDetail)
def zone_detail(cell: str) -> ZoneDetail:
    detail = get_store().zone_detail(cell)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Unknown H3 cell '{cell}'.")
    return ZoneDetail(**detail)


@router.get("/stats", response_model=StatsResponse)
def stats(resolution: int = Query(default=8, ge=0, le=15)) -> StatsResponse:
    _validate_resolution(resolution)
    df = get_store().frame(resolution)
    return StatsResponse(
        resolution=resolution,
        zone_count=len(df),
        safety_mean=round(float(df["safety_score"].mean()), 1),
        safety_p10=round(float(df["safety_score"].quantile(0.1)), 1),
        safety_p90=round(float(df["safety_score"].quantile(0.9)), 1),
        calmness_mean=round(float(df["calmness_score"].mean()), 1),
        calmness_p10=round(float(df["calmness_score"].quantile(0.1)), 1),
        calmness_p90=round(float(df["calmness_score"].quantile(0.9)), 1),
        profiles=df["profile"].value_counts().to_dict(),
    )


@router.get("/weights")
def weights() -> dict:
    """Default model weights (frontend seeds the simulation sliders from these)."""
    return {
        "features": list(FEATURES),
        "safety_weights": SAFETY_WEIGHTS,
        "calmness_weights": CALMNESS_WEIGHTS,
    }


@router.post("/simulate", response_model=SimulationResponse)
def simulate(request: SimulationRequest) -> SimulationResponse:
    """Recompute scores with user-supplied weight overrides (what-if analysis)."""
    _validate_resolution(request.resolution)
    unknown = [f for f in {**request.safety_weights, **request.calmness_weights} if f not in FEATURES]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown features: {unknown}")
    df = get_store().frame(request.resolution)
    counts = df[[f for f in FEATURES if f in df.columns]]
    scores = compute_scores(counts, request.safety_weights, request.calmness_weights)
    return SimulationResponse(
        resolution=request.resolution,
        applied_safety_weights={**SAFETY_WEIGHTS, **request.safety_weights},
        applied_calmness_weights={**CALMNESS_WEIGHTS, **request.calmness_weights},
        zones=[
            ZoneScore(h3=cell, safety_score=row["safety_score"], calmness_score=row["calmness_score"])
            for cell, row in scores.iterrows()
        ],
    )
