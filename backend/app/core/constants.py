"""Domain constants: urban feature taxonomy and OSM tag mapping."""

from __future__ import annotations

# Canonical urban feature categories counted per H3 cell.
FEATURES: tuple[str, ...] = (
    "streetlight",
    "police_fire",
    "transit_stop",
    "school",
    "park_green",
    "bar_nightlife",
    "restaurant_cafe",
    "shop_retail",
    "industrial",
    "major_road",
)

# OSM tag queries per feature category (osmnx `features_from_polygon` format).
OSM_TAGS: dict[str, dict[str, object]] = {
    "streetlight": {"highway": "street_lamp"},
    "police_fire": {"amenity": ["police", "fire_station"]},
    "transit_stop": {"highway": "bus_stop", "public_transport": "platform"},
    "school": {"amenity": ["school", "kindergarten", "college", "university"]},
    "park_green": {"leisure": ["park", "garden", "playground"], "landuse": "grass"},
    "bar_nightlife": {"amenity": ["bar", "pub", "nightclub"]},
    "restaurant_cafe": {"amenity": ["restaurant", "cafe", "fast_food"]},
    "shop_retail": {"shop": True},
    "industrial": {"landuse": "industrial"},
    "major_road": {"highway": ["motorway", "trunk", "primary", "secondary"]},
}

# Synthetic-mode expected intensity per feature at the downtown core
# (events per res-9 hex), decaying with distance from downtown.
SYNTHETIC_LAMBDA: dict[str, float] = {
    "streetlight": 14.0,
    "police_fire": 0.35,
    "transit_stop": 3.5,
    "school": 0.6,
    "park_green": 1.2,
    "bar_nightlife": 2.5,
    "restaurant_cafe": 4.0,
    "shop_retail": 6.0,
    "industrial": 0.8,
    "major_road": 2.0,
}

# Fraction of the synthetic intensity that is distance-independent (uniform floor).
SYNTHETIC_UNIFORM_FLOOR: dict[str, float] = {
    "streetlight": 0.35,
    "police_fire": 0.20,
    "transit_stop": 0.30,
    "school": 0.45,
    "park_green": 0.60,
    "bar_nightlife": 0.05,
    "restaurant_cafe": 0.15,
    "shop_retail": 0.15,
    "industrial": 0.30,
    "major_road": 0.40,
}
