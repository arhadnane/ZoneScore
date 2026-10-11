"""Live OSM feature acquisition for a single H3 cell on demand."""

from __future__ import annotations

import json
import ssl
import urllib.request
from typing import Any

import h3

from app.core.constants import FEATURES
from app.core.logging import get_logger

log = get_logger(__name__)

# Cache live results in-memory so repeated clicks on the same zone don't re-hit OSM
_LIVE_CACHE: dict[str, dict[str, Any]] = {}


def fetch_live_cell_features(cell: str) -> dict[str, Any]:
    """Fetch live OpenStreetMap features covering the exact bounds of an H3 cell.

    Uses the high-availability OpenStreetMap REST API (api.openstreetmap.org)
    which returns live nodes/ways/relations with tags in < 1 second.
    """
    if cell in _LIVE_CACHE:
        return _LIVE_CACHE[cell]

    # Get boundary polygon from H3
    boundary = h3.cell_to_boundary(cell)
    lats = [pt[0] for pt in boundary]
    lngs = [pt[1] for pt in boundary]
    min_lat, max_lat = min(lats), max(lats)
    min_lng, max_lng = min(lngs), max(lngs)

    # Pad slightly to capture edge amenities
    pad = 0.0005
    url = (
        f"https://api.openstreetmap.org/api/0.6/map.json?"
        f"bbox={min_lng - pad},{min_lat - pad},{max_lng + pad},{max_lat + pad}"
    )

    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "URBIS-GeoSafe/1.0 (Live Urban Analysis; OpenStreetMap client)",
            "Accept": "application/json",
        },
    )

    counts = {f: 0 for f in FEATURES}
    pois: list[dict[str, str]] = []

    try:
        with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elements = data.get("elements", [])

            for el in elements:
                tags = el.get("tags")
                if not tags:
                    continue

                amenity = tags.get("amenity", "")
                leisure = tags.get("leisure", "")
                shop = tags.get("shop", "")
                highway = tags.get("highway", "")
                landuse = tags.get("landuse", "")

                matched = False
                name = tags.get("name", "")

                # Streetlights
                if highway == "street_lamp":
                    counts["streetlight"] += 1
                    matched = True

                # Police & Fire
                if amenity in ("police", "fire_station"):
                    counts["police_fire"] += 1
                    matched = True

                # Transit stops
                if highway in ("bus_stop", "platform") or tags.get("public_transport"):
                    counts["transit_stop"] += 1
                    matched = True

                # Schools & Universities
                if amenity in ("school", "kindergarten", "college", "university"):
                    counts["school"] += 1
                    matched = True

                # Parks & Green areas
                if leisure in ("park", "garden", "playground") or landuse == "grass":
                    counts["park_green"] += 1
                    matched = True

                # Nightlife
                if amenity in ("bar", "pub", "nightclub"):
                    counts["bar_nightlife"] += 1
                    matched = True

                # Restaurants & Cafes
                if amenity in ("restaurant", "cafe", "fast_food"):
                    counts["restaurant_cafe"] += 1
                    matched = True

                # Retail & Shops
                if shop:
                    counts["shop_retail"] += 1
                    matched = True

                # Industrial
                if landuse == "industrial":
                    counts["industrial"] += 1
                    matched = True

                # Major roads
                if highway in ("motorway", "trunk", "primary", "secondary"):
                    counts["major_road"] += 1
                    matched = True

                if matched and name and len(pois) < 25:
                    label = (
                        amenity
                        or shop
                        or leisure
                        or (highway if highway != "street_lamp" else "Éclairage")
                    )
                    pois.append({"name": name, "type": label})

            result = {
                "live": True,
                "counts": counts,
                "poi_samples": pois,
                "total_live_elements": len(elements),
            }
            _LIVE_CACHE[cell] = result
            return result

    except Exception as exc:
        log.warning("Live OSM acquisition failed for cell %s: %s", cell, exc)
        return {
            "live": False,
            "error": str(exc),
            "counts": {},
            "poi_samples": [],
            "total_live_elements": 0,
        }
