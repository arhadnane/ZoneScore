"""H3 grid generation over the Québec City territory."""

from __future__ import annotations

import math

import h3
from shapely.geometry import Polygon, box

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


def fallback_boundary(
    settings: Settings | None = None, city: str | None = None
) -> Polygon:
    """Bounding-box polygon covering the city core (offline fallback)."""
    if city:
        from app.core.cities import get_city

        c = get_city(city)
        return box(c.bbox_west, c.bbox_south, c.bbox_east, c.bbox_north)
    s = settings or get_settings()
    return box(s.bbox_west, s.bbox_south, s.bbox_east, s.bbox_north)


def get_city_boundary(
    settings: Settings | None = None, city: str | None = None
) -> Polygon:
    """Resolve the city boundary via OSM geocoding, falling back to the bbox."""
    s = settings or get_settings()
    if s.offline or city:
        # Use city bbox boundary: fast, focused on urban core, immune to Overpass timeouts
        return fallback_boundary(s, city=city)
    query = s.city_query
    try:
        import osmnx as ox

        ox.settings.use_cache = True
        ox.settings.cache_folder = str(s.raw_dir / "osmnx_cache")
        gdf = ox.geocode_to_gdf(query)
        geom = gdf.geometry.iloc[0]
        poly = geom if isinstance(geom, Polygon) else max(geom.geoms, key=lambda g: g.area)
        log.info("Resolved city boundary for '%s' from OSM (area=%.4f deg^2).", query, poly.area)
        return poly
    except Exception as exc:  # network / geocoding failure -> deterministic fallback
        log.warning("Boundary geocoding failed for '%s' (%s); using bbox fallback.", query, exc)
        return fallback_boundary(s, city=city)


def generate_grid(boundary: Polygon, resolution: int) -> list[str]:
    """Return sorted H3 cell ids covering ``boundary`` at ``resolution``."""
    cells = sorted(h3.geo_to_cells(boundary, resolution))
    log.info("Generated %d H3 cells at resolution %d.", len(cells), resolution)
    return cells


def cell_centroid(cell: str) -> tuple[float, float]:
    """(lat, lng) centroid of an H3 cell."""
    return h3.cell_to_latlng(cell)


def cell_polygon_coords(cell: str) -> list[list[float]]:
    """Closed GeoJSON ring ([lng, lat] pairs) for an H3 cell boundary."""
    ring = [[lng, lat] for lat, lng in h3.cell_to_boundary(cell)]
    ring.append(ring[0])
    return ring


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
