"""API routes: zones, scores, statistics, what-if simulation, and Canadian cities."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import (
    CityInfo,
    HealthResponse,
    SimulationRequest,
    SimulationResponse,
    StatsResponse,
    ZoneDetail,
    ZoneScore,
)
from app.api.store import get_store
from app.core.cities import (
    COUNTRY_NAMES,
    REGION_NAMES,
    find_city_by_coords,
    get_city,
    list_cities,
)
from app.core.config import get_settings
from app.core.constants import FEATURES
from app.models.scoring import (
    CALMNESS_WEIGHTS,
    FAMILY_WEIGHTS,
    SAFETY_WEIGHTS,
    compute_scores_from_scaled,
)

router = APIRouter(prefix="/api")


def _validate_resolution(resolution: int, city: str = "quebec") -> None:
    c = get_city(city).id
    store = get_store()
    if (c, resolution) not in store._frames:
        store.load_city(c, run_etl_if_missing=False)
    if (c, resolution) not in store._frames:
        raise HTTPException(
            status_code=404,
            detail=f"No data for resolution {resolution} in city '{city}'.",
        )


@router.get("/cities", response_model=list[CityInfo])
def get_cities() -> list[CityInfo]:
    """List supported metropolitan cities with their country / province (state)."""
    return [
        CityInfo(
            id=c.id,
            name=c.name,
            province=c.province,
            country=c.country,
            country_name=COUNTRY_NAMES.get(c.country, c.country),
            province_name=REGION_NAMES.get((c.country, c.province), c.province),
            center=c.center,
            default_zoom=c.default_zoom,
            bounds=c.bounds_coords,
        )
        for c in list_cities()
    ]


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
        cities=store.loaded_cities(),
    )


@router.get("/zones")
def zones(
    city: str = Query(default="quebec", description="Canadian city id"),
    resolution: int = Query(default=8, ge=0, le=15),
) -> dict:
    """GeoJSON FeatureCollection of scored H3 zones for a Canadian city."""
    _validate_resolution(resolution, city=city)
    return get_store().geojson(resolution, city=city)


@router.get("/zones/{cell}", response_model=ZoneDetail)
def zone_detail(
    cell: str,
    city: str | None = Query(default=None, description="Optional city hint"),
    live: bool = Query(default=True, description="Enrich with live OpenStreetMap data for this cell"),
) -> ZoneDetail:
    detail = get_store().zone_detail(cell, city=city)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Unknown H3 cell '{cell}'.")

    if live:
        from app.etl.live_osm import fetch_live_cell_features

        live_res = fetch_live_cell_features(cell)
        if live_res.get("live") and live_res.get("counts"):
            # Update counts with live OSM counts where available
            detail["counts"] = {**detail.get("counts", {}), **live_res["counts"]}
            detail["live_active"] = True
            detail["live_poi_samples"] = live_res.get("poi_samples", [])
            detail["live_total_elements"] = live_res.get("total_live_elements", 0)

    return ZoneDetail(**detail)


@router.get("/stats", response_model=StatsResponse)
def stats(
    city: str = Query(default="quebec", description="Canadian city id"),
    resolution: int = Query(default=8, ge=0, le=15),
) -> StatsResponse:
    _validate_resolution(resolution, city=city)
    df = get_store().frame(resolution, city=city)
    fam_col = df["family_score"] if "family_score" in df.columns else df["safety_score"]
    return StatsResponse(
        resolution=resolution,
        zone_count=len(df),
        safety_mean=round(float(df["safety_score"].mean()), 1),
        safety_p10=round(float(df["safety_score"].quantile(0.1)), 1),
        safety_p90=round(float(df["safety_score"].quantile(0.9)), 1),
        calmness_mean=round(float(df["calmness_score"].mean()), 1),
        calmness_p10=round(float(df["calmness_score"].quantile(0.1)), 1),
        calmness_p90=round(float(df["calmness_score"].quantile(0.9)), 1),
        family_mean=round(float(fam_col.mean()), 1),
        family_p10=round(float(fam_col.quantile(0.1)), 1),
        family_p90=round(float(fam_col.quantile(0.9)), 1),
        profiles=df["profile"].value_counts().to_dict(),
        city=city,
    )


@router.get("/weights")
def weights() -> dict:
    """Default model weights (frontend seeds the simulation sliders from these)."""
    return {
        "features": list(FEATURES),
        "safety_weights": SAFETY_WEIGHTS,
        "calmness_weights": CALMNESS_WEIGHTS,
        "family_weights": FAMILY_WEIGHTS,
    }


@router.post("/simulate", response_model=SimulationResponse)
def simulate(request: SimulationRequest) -> SimulationResponse:
    """Recompute scores with user-supplied weight overrides (what-if analysis)."""
    _validate_resolution(request.resolution, city=request.city)
    all_overrides = {
        **request.safety_weights,
        **request.calmness_weights,
        **request.family_weights,
    }
    unknown = [f for f in all_overrides if f not in FEATURES]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown features: {unknown}")
    scaled = get_store().scaled_frame(request.resolution, city=request.city)
    scores = compute_scores_from_scaled(
        scaled,
        request.safety_weights,
        request.calmness_weights,
        request.family_weights,
    )
    return SimulationResponse(
        resolution=request.resolution,
        city=request.city,
        applied_safety_weights={**SAFETY_WEIGHTS, **request.safety_weights},
        applied_calmness_weights={**CALMNESS_WEIGHTS, **request.calmness_weights},
        applied_family_weights={**FAMILY_WEIGHTS, **request.family_weights},
        zones=[
            ZoneScore(h3=cell, safety_score=s, calmness_score=c, family_score=fam)
            for cell, s, c, fam in zip(
                scores.index,
                scores["safety_score"],
                scores["calmness_score"],
                scores["family_score"],
                strict=False,
            )
        ],
    )


@router.get("/locate")
def locate(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    resolution: int = Query(default=8, ge=0, le=15),
    city: str | None = Query(default=None, description="Optional city target"),
) -> dict:
    """Find the H3 cell at the given coordinates in the matched or targeted Canadian city."""
    import h3

    from app.etl.grid import cell_centroid, haversine_km

    # If city is not explicitly specified, auto-detect the Canadian city
    matched_city = get_city(city) if city else find_city_by_coords(lat, lng)
    cid = matched_city.id

    cell = h3.latlng_to_cell(lat, lng, resolution)
    detail = get_store().zone_detail(cell, city=cid)
    if detail is not None:
        return {
            "h3": cell,
            "city": cid,
            "city_name": matched_city.name,
            "found": True,
            "detail": detail,
        }

    try:
        df = get_store().frame(resolution, city=cid)
    except KeyError:
        df = None

    if df is not None and not df.empty:
        closest_cell = None
        min_dist = float("inf")
        for c in df.index:
            clat, clng = cell_centroid(c)
            d = haversine_km(lat, lng, clat, clng)
            if d < min_dist:
                min_dist = d
                closest_cell = c

        if closest_cell is not None:
            return {
                "h3": closest_cell,
                "city": cid,
                "city_name": matched_city.name,
                "found": True,
                "closest": True,
                "distance_km": round(min_dist, 2),
                "detail": get_store().zone_detail(closest_cell, city=cid),
            }

    raise HTTPException(status_code=404, detail=f"No matching zone found near ({lat}, {lng}).")
