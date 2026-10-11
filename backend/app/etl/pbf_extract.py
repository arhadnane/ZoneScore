"""Extract real OSM points and geometries from local PBF file for a specific city boundary."""

from __future__ import annotations

from pathlib import Path
import duckdb
import pandas as pd
from shapely.geometry import Point, Polygon
import h3

from app.core.constants import FEATURES
from app.core.logging import get_logger

log = get_logger(__name__)


def extract_city_features_from_pbf(
    pbf_path: Path,
    boundary: Polygon,
    cells: list[str],
    resolution: int,
) -> pd.DataFrame:
    """Read local OSM PBF using DuckDB spatial, filter by boundary bbox and tags, and bin into H3 cells."""
    minx, miny, maxx, maxy = boundary.bounds

    log.info("Extracting features from %s in bbox (%.3f, %.3f, %.3f, %.3f)...", pbf_path.name, minx, miny, maxx, maxy)

    con = duckdb.connect()
    con.execute("LOAD spatial;")

    # Query nodes inside the bbox with tags relevant to our features
    query = f"""
    SELECT 
        id,
        lat,
        lon,
        element_at(tags, 'highway') AS tag_highway,
        element_at(tags, 'amenity') AS tag_amenity,
        element_at(tags, 'shop') AS tag_shop,
        element_at(tags, 'leisure') AS tag_leisure,
        element_at(tags, 'landuse') AS tag_landuse
    FROM ST_ReadOSM('{pbf_path.as_posix()}')
    WHERE kind = 'node'
      AND lat BETWEEN {miny} AND {maxy}
      AND lon BETWEEN {minx} AND {maxx}
      AND (
          element_at(tags, 'highway') IS NOT NULL
          OR element_at(tags, 'amenity') IS NOT NULL
          OR element_at(tags, 'shop') IS NOT NULL
          OR element_at(tags, 'leisure') IS NOT NULL
          OR element_at(tags, 'landuse') IS NOT NULL
      )
    """

    df_nodes = con.execute(query).df()
    log.info("Extracted %d tagged nodes in city bbox from PBF.", len(df_nodes))

    df = pd.DataFrame(index=pd.Index(cells, name="h3"))
    valid_cells = set(cells)
    counts = {f: {c: 0 for c in cells} for f in FEATURES}

    # Map each node to its H3 cell and match features
    for _, row in df_nodes.iterrows():
        lat, lon = row["lat"], row["lon"]
        cell = h3.latlng_to_cell(lat, lon, resolution)
        if cell not in valid_cells:
            continue

        def _tag(val) -> str:
            if val is None:
                return ""
            if hasattr(val, "__len__") and len(val) == 0:
                return ""
            return str(val)

        hwy = _tag(row["tag_highway"])
        amenity = _tag(row["tag_amenity"])
        shop = _tag(row["tag_shop"])
        leisure = _tag(row["tag_leisure"])
        landuse = _tag(row["tag_landuse"])

        if hwy == "street_lamp":
            counts["streetlight"][cell] += 1
        if amenity in ("police", "fire_station"):
            counts["police_fire"][cell] += 1
        if hwy in ("bus_stop", "platform"):
            counts["transit_stop"][cell] += 1
        if amenity in ("school", "kindergarten", "college", "university"):
            counts["school"][cell] += 1
        if leisure in ("park", "garden", "playground") or landuse == "grass":
            counts["park_green"][cell] += 1
        if amenity in ("bar", "pub", "nightclub"):
            counts["bar_nightlife"][cell] += 1
        if amenity in ("restaurant", "cafe", "fast_food"):
            counts["restaurant_cafe"][cell] += 1
        if shop and shop != "None":
            counts["shop_retail"][cell] += 1
        if landuse == "industrial":
            counts["industrial"][cell] += 1
        if hwy in ("motorway", "trunk", "primary", "secondary"):
            counts["major_road"][cell] += 1

    for feature in FEATURES:
        df[feature] = pd.Series(counts[feature])

    log.info("Built 100%% real PBF counts for %d cells (res %d). Total features found: %d",
             len(df), resolution, df[list(FEATURES)].to_numpy().sum())
    return df
