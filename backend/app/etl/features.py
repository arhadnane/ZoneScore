"""Urban feature acquisition: OSM (osmnx) with deterministic synthetic fallback."""
from __future__ import annotations

import hashlib
import math

import h3
import pandas as pd
from shapely.geometry import Polygon

from app.core.config import Settings, get_settings
from app.core.constants import FEATURES, OSM_TAGS, SYNTHETIC_LAMBDA, SYNTHETIC_UNIFORM_FLOOR
from app.core.logging import get_logger
from app.etl.grid import cell_centroid, haversine_km

log = get_logger(__name__)

_DECAY_KM = 6.0  # e-folding distance of the downtown density gradient


def _unit_hash(cell: str, feature: str) -> float:
    """Deterministic pseudo-random float in [0, 1) from (cell, feature)."""
    digest = hashlib.sha256(f"{cell}:{feature}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def synthetic_counts(cells: list[str], resolution: int, settings: Settings | None = None) -> pd.DataFrame:
    """Reproducible synthetic feature counts with a downtown-distance gradient."""
    s = settings or get_settings()
    # Res-8 hexes cover ~7x the area of res-9 hexes -> scale intensities accordingly.
    area_scale = 7.0 ** (9 - resolution)
    rows: list[dict[str, object]] = []
    for cell in cells:
        lat, lng = cell_centroid(cell)
        dist = haversine_km(lat, lng, s.downtown_lat, s.downtown_lng)
        gradient = math.exp(-dist / _DECAY_KM)
        row: dict[str, object] = {"h3": cell}
        for feature in FEATURES:
            lam = SYNTHETIC_LAMBDA[feature] * area_scale
            floor = SYNTHETIC_UNIFORM_FLOOR[feature]
            intensity = lam * (floor + (1.0 - floor) * gradient)
            # Deterministic draw: scale intensity by a hash-based factor in [0.25, 1.75).
            factor = 0.25 + 1.5 * _unit_hash(cell, feature)
            row[feature] = int(round(intensity * factor))
        rows.append(row)
    df = pd.DataFrame(rows).set_index("h3")
    log.info("Synthesised counts for %d cells (res %d).", len(df), resolution)
    return df


def _fetch_osm_points(boundary: Polygon, settings: Settings) -> dict[str, pd.DataFrame]:
    """Fetch representative points per feature category from OSM."""
    import osmnx as ox

    ox.settings.use_cache = True
    ox.settings.cache_folder = str(settings.raw_dir / "osmnx_cache")
    ox.settings.log_console = False

    points: dict[str, pd.DataFrame] = {}
    for feature, tags in OSM_TAGS.items():
        gdf = ox.features_from_polygon(boundary, tags)
        if gdf.empty:
            points[feature] = pd.DataFrame(columns=["lat", "lng"])
            continue
        reps = gdf.geometry.representative_point()
        points[feature] = pd.DataFrame({"lat": reps.y.values, "lng": reps.x.values})
        log.info("OSM: %s -> %d features.", feature, len(gdf))
    return points


def _aggregate_points(points: dict[str, pd.DataFrame], cells: list[str], resolution: int) -> pd.DataFrame:
    """Bin feature points into H3 cells and align with the grid index."""
    df = pd.DataFrame(index=pd.Index(cells, name="h3"))
    for feature in FEATURES:
        pts = points.get(feature)
        if pts is None or pts.empty:
            df[feature] = 0
            continue
        assigned = [h3.latlng_to_cell(lat, lng, resolution) for lat, lng in zip(pts["lat"], pts["lng"])]
        counts = pd.Series(assigned).value_counts()
        df[feature] = counts.reindex(df.index).fillna(0).astype(int)
    return df


def build_feature_counts(
    boundary: Polygon,
    cells: list[str],
    resolution: int,
    settings: Settings | None = None,
) -> pd.DataFrame:
    """Feature counts per cell — OSM when reachable, synthetic otherwise."""
    s = settings or get_settings()
    if not s.offline:
        try:
            points = _fetch_osm_points(boundary, s)
            df = _aggregate_points(points, cells, resolution)
            if df[list(FEATURES)].to_numpy().sum() > 0:
                log.info("Built OSM-based counts for %d cells (res %d).", len(df), resolution)
                return df
            log.warning("OSM returned no in-grid features; switching to synthetic mode.")
        except Exception as exc:
            log.warning("OSM acquisition failed (%s); switching to synthetic mode.", exc)
    return synthetic_counts(cells, resolution, s)
