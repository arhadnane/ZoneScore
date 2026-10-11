"""Urban feature acquisition: OSM (osmnx) with deterministic synthetic fallback."""

from __future__ import annotations

import hashlib
import math

import h3
import pandas as pd
from shapely.geometry import Polygon

from app.core.config import Settings, get_settings
from app.core.constants import (
    FEATURES,
    OSM_TAGS,
    SYNTHETIC_LAMBDA,
    SYNTHETIC_UNIFORM_FLOOR,
)
from app.core.logging import get_logger
from app.etl.grid import cell_centroid, haversine_km

log = get_logger(__name__)

_DECAY_KM = 6.0  # e-folding distance of the downtown density gradient


def _unit_hash(cell: str, feature: str) -> float:
    """Deterministic pseudo-random float in [0, 1) from (cell, feature)."""
    digest = hashlib.sha256(f"{cell}:{feature}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def synthetic_counts(
    cells: list[str],
    resolution: int,
    settings: Settings | None = None,
    city: str | None = None,
) -> pd.DataFrame:
    """Reproducible synthetic feature counts with a downtown-distance gradient."""
    s = settings or get_settings()
    d_lat, d_lng = s.downtown_lat, s.downtown_lng
    if city:
        from app.core.cities import get_city

        c = get_city(city)
        d_lat, d_lng = c.downtown_lat, c.downtown_lng

    # Res-8 hexes cover ~7x the area of res-9 hexes -> scale intensities accordingly.
    area_scale = 7.0 ** (9 - resolution)
    rows: list[dict[str, object]] = []
    for cell in cells:
        lat, lng = cell_centroid(cell)
        dist = haversine_km(lat, lng, d_lat, d_lng)
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
    log.info(
        "Synthesised counts for %d cells (res %d, city %s).",
        len(df),
        resolution,
        city or "default",
    )
    return df


def _fetch_osm_geometries(boundary: Polygon, settings: Settings) -> dict[str, list]:
    """Fetch feature geometries per category from OSM."""
    import osmnx as ox

    ox.settings.use_cache = True
    ox.settings.cache_folder = str(settings.raw_dir / "osmnx_cache")
    ox.settings.log_console = False

    geometries: dict[str, list] = {}
    for feature, tags in OSM_TAGS.items():
        gdf = ox.features_from_polygon(boundary, tags)
        if gdf.empty:
            geometries[feature] = []
            continue
        geometries[feature] = list(gdf.geometry.dropna())
        log.info("OSM: %s -> %d features.", feature, len(gdf))
    return geometries


def _aggregate_geometries(
    geometries: dict[str, list],
    cells: list[str],
    resolution: int,
) -> pd.DataFrame:
    """Bin feature geometries into H3 cells:
    - Polygons/MultiPolygons (e.g. large parks, industrial areas) expand across all covered cells.
    - Points and lines map to their representative H3 cell.
    """
    df = pd.DataFrame(index=pd.Index(cells, name="h3"))
    valid_cells = set(cells)

    for feature in FEATURES:
        geoms = geometries.get(feature, [])
        if not geoms:
            df[feature] = 0
            continue

        assigned: list[str] = []
        for geom in geoms:
            if geom.is_empty:
                continue
            if geom.geom_type in ("Polygon", "MultiPolygon"):
                sub_polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
                poly_cells: set[str] = set()
                for p in sub_polys:
                    try:
                        poly_cells.update(h3.geo_to_cells(p, resolution))
                    except Exception:
                        pass
                if poly_cells:
                    assigned.extend(c for c in poly_cells if c in valid_cells)
                else:
                    rep = geom.representative_point()
                    cell = h3.latlng_to_cell(rep.y, rep.x, resolution)
                    if cell in valid_cells:
                        assigned.append(cell)
            elif geom.geom_type == "Point":
                cell = h3.latlng_to_cell(geom.y, geom.x, resolution)
                if cell in valid_cells:
                    assigned.append(cell)
            else:
                rep = geom.representative_point()
                cell = h3.latlng_to_cell(rep.y, rep.x, resolution)
                if cell in valid_cells:
                    assigned.append(cell)

        counts = pd.Series(assigned).value_counts()
        df[feature] = counts.reindex(df.index).fillna(0).astype(int)

    return df


# Aliases for backward compatibility
_fetch_osm_points = _fetch_osm_geometries
_aggregate_points = _aggregate_geometries


_BOUNDARY_GEOMS_CACHE: dict[str, dict[str, list]] = {}


def build_feature_counts(
    boundary: Polygon,
    cells: list[str],
    resolution: int,
    settings: Settings | None = None,
    city: str | None = None,
) -> pd.DataFrame:
    """Feature counts per cell — OSM when reachable, synthetic otherwise."""
    s = settings or get_settings()
    # Priority 1: Check for local Geofabrik PBF extracts (100% offline, ultra-fast, 100% real)
    pbf_candidates = list(s.raw_dir.glob("*.osm.pbf"))
    if pbf_candidates:
        from app.etl.pbf_extract import extract_city_features_from_pbf

        for pbf_path in pbf_candidates:
            try:
                df = extract_city_features_from_pbf(pbf_path, boundary, cells, resolution)
                if df[list(FEATURES)].to_numpy().sum() > 0:
                    return df
            except Exception as pbf_err:
                log.warning("PBF extraction from %s failed: %s", pbf_path.name, pbf_err)

    if not s.offline:
        try:
            b_key = f"{city or 'default'}:{boundary.bounds}"
            if b_key not in _BOUNDARY_GEOMS_CACHE:
                _BOUNDARY_GEOMS_CACHE[b_key] = _fetch_osm_geometries(boundary, s)
            geoms = _BOUNDARY_GEOMS_CACHE[b_key]
            df = _aggregate_geometries(geoms, cells, resolution)
            if df[list(FEATURES)].to_numpy().sum() > 0:
                log.info(
                    "Built OSM-based counts for %d cells (res %d, city %s).",
                    len(df),
                    resolution,
                    city or "default",
                )
                return df
            log.warning("OSM returned no in-grid features; switching to synthetic mode.")
        except Exception as exc:
            log.warning("OSM acquisition failed (%s); switching to synthetic mode.", exc)
    return synthetic_counts(cells, resolution, s, city=city)
