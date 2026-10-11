"""Metropolitan cities configuration and spatial bounding boxes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from shapely.geometry import Polygon, box


@dataclass(frozen=True)
class CityConfig:
    id: str
    name: str
    province: str
    city_query: str
    bbox_west: float
    bbox_south: float
    bbox_east: float
    bbox_north: float
    downtown_lat: float
    downtown_lng: float
    default_zoom: float
    country: str = "CA"

    @property
    def boundary_box(self) -> Polygon:
        return box(self.bbox_west, self.bbox_south, self.bbox_east, self.bbox_north)

    @property
    def center(self) -> tuple[float, float]:
        """(latitude, longitude) center of the city."""
        return (self.downtown_lat, self.downtown_lng)

    @property
    def bounds_coords(self) -> tuple[float, float, float, float]:
        """(west, south, east, north) tuple."""
        return (self.bbox_west, self.bbox_south, self.bbox_east, self.bbox_north)

    def contains(self, lat: float, lng: float) -> bool:
        """Return True if (lat, lng) falls inside this city's bounding box."""
        return (
            self.bbox_south <= lat <= self.bbox_north
            and self.bbox_west <= lng <= self.bbox_east
        )


# Display names for the country -> province/state -> city hierarchy
COUNTRY_NAMES: dict[str, str] = {"CA": "Canada", "US": "United States"}

REGION_NAMES: dict[tuple[str, str], str] = {
    ("CA", "QC"): "Québec",
    ("CA", "ON"): "Ontario",
    ("CA", "BC"): "British Columbia",
    ("CA", "AB"): "Alberta",
    ("US", "NY"): "New York",
    ("US", "CA"): "California",
    ("US", "IL"): "Illinois",
    ("US", "WA"): "Washington",
    ("US", "MA"): "Massachusetts",
    ("US", "TX"): "Texas",
}


# Major metropolitan areas supported by URBIS (Canada & USA)
CITIES: dict[str, CityConfig] = {
    "quebec": CityConfig(
        id="quebec",
        name="Québec",
        province="QC",
        city_query="Québec (ville), Québec, Canada",
        bbox_west=-71.415,
        bbox_south=46.720,
        bbox_east=-71.130,
        bbox_north=46.905,
        downtown_lat=46.8131,
        downtown_lng=-71.2075,
        default_zoom=11.5,
    ),
    "montreal": CityConfig(
        id="montreal",
        name="Montréal",
        province="QC",
        city_query="Montréal, Québec, Canada",
        bbox_west=-73.700,
        bbox_south=45.440,
        bbox_east=-73.510,
        bbox_north=45.580,
        downtown_lat=45.5017,
        downtown_lng=-73.5673,
        default_zoom=12.0,
    ),
    "ottawa": CityConfig(
        id="ottawa",
        name="Ottawa - Gatineau",
        province="ON",
        city_query="Ottawa, Ontario, Canada",
        bbox_west=-75.770,
        bbox_south=45.360,
        bbox_east=-75.630,
        bbox_north=45.460,
        downtown_lat=45.4215,
        downtown_lng=-75.6972,
        default_zoom=12.2,
    ),
    "toronto": CityConfig(
        id="toronto",
        name="Toronto",
        province="ON",
        city_query="Toronto, Ontario, Canada",
        bbox_west=-79.460,
        bbox_south=43.620,
        bbox_east=-79.330,
        bbox_north=43.710,
        downtown_lat=43.6532,
        downtown_lng=-79.3832,
        default_zoom=12.2,
    ),
    "vancouver": CityConfig(
        id="vancouver",
        name="Vancouver",
        province="BC",
        city_query="Vancouver, British Columbia, Canada",
        bbox_west=-123.180,
        bbox_south=49.230,
        bbox_east=-123.050,
        bbox_north=49.310,
        downtown_lat=49.2827,
        downtown_lng=-123.1207,
        default_zoom=12.2,
    ),
    "calgary": CityConfig(
        id="calgary",
        name="Calgary",
        province="AB",
        city_query="Calgary, Alberta, Canada",
        bbox_west=-114.200,
        bbox_south=50.980,
        bbox_east=-113.960,
        bbox_north=51.120,
        downtown_lat=51.0447,
        downtown_lng=-114.0719,
        default_zoom=11.8,
    ),
    "edmonton": CityConfig(
        id="edmonton",
        name="Edmonton",
        province="AB",
        city_query="Edmonton, Alberta, Canada",
        bbox_west=-113.620,
        bbox_south=53.480,
        bbox_east=-113.370,
        bbox_north=53.620,
        downtown_lat=53.5461,
        downtown_lng=-113.4938,
        default_zoom=11.8,
    ),
    "newyork": CityConfig(
        id="newyork",
        name="New York",
        province="NY",
        city_query="New York City, New York, USA",
        bbox_west=-74.030,
        bbox_south=40.700,
        bbox_east=-73.920,
        bbox_north=40.800,
        downtown_lat=40.7580,
        downtown_lng=-73.9855,
        default_zoom=12.2,
        country="US",
    ),
    "losangeles": CityConfig(
        id="losangeles",
        name="Los Angeles",
        province="CA",
        city_query="Los Angeles, California, USA",
        bbox_west=-118.350,
        bbox_south=33.980,
        bbox_east=-118.150,
        bbox_north=34.120,
        downtown_lat=34.0522,
        downtown_lng=-118.2437,
        default_zoom=11.6,
        country="US",
    ),
    "chicago": CityConfig(
        id="chicago",
        name="Chicago",
        province="IL",
        city_query="Chicago, Illinois, USA",
        bbox_west=-87.760,
        bbox_south=41.810,
        bbox_east=-87.580,
        bbox_north=41.960,
        downtown_lat=41.8781,
        downtown_lng=-87.6298,
        default_zoom=11.8,
        country="US",
    ),
    "seattle": CityConfig(
        id="seattle",
        name="Seattle",
        province="WA",
        city_query="Seattle, Washington, USA",
        bbox_west=-122.400,
        bbox_south=47.570,
        bbox_east=-122.270,
        bbox_north=47.680,
        downtown_lat=47.6062,
        downtown_lng=-122.3321,
        default_zoom=12.0,
        country="US",
    ),
    "boston": CityConfig(
        id="boston",
        name="Boston",
        province="MA",
        city_query="Boston, Massachusetts, USA",
        bbox_west=-71.140,
        bbox_south=42.320,
        bbox_east=-71.020,
        bbox_north=42.400,
        downtown_lat=42.3601,
        downtown_lng=-71.0589,
        default_zoom=12.2,
        country="US",
    ),
    "houston": CityConfig(
        id="houston",
        name="Houston",
        province="TX",
        city_query="Houston, Texas, USA",
        bbox_west=-95.450,
        bbox_south=29.690,
        bbox_east=-95.290,
        bbox_north=29.810,
        downtown_lat=29.7604,
        downtown_lng=-95.3698,
        default_zoom=11.8,
        country="US",
    ),
}

DEFAULT_CITY_ID = "quebec"


def get_city(city_id: str | None = None) -> CityConfig:
    """Return the requested city configuration or the default (quebec)."""
    if not city_id:
        return CITIES[DEFAULT_CITY_ID]
    normalized = city_id.lower().strip()
    if normalized not in CITIES:
        raise KeyError(f"Unknown city '{city_id}'. Available: {list(CITIES.keys())}")
    return CITIES[normalized]


def list_cities() -> Sequence[CityConfig]:
    """Return all configured metropolitan cities."""
    return tuple(CITIES.values())


def find_city_by_coords(lat: float, lng: float) -> CityConfig:
    """Find the city whose bounding box contains the coordinates, or the closest one."""
    for city in CITIES.values():
        if city.contains(lat, lng):
            return city
    # Fallback to closest city by Euclidean distance to downtown
    import math

    def dist(c: CityConfig) -> float:
        return math.hypot(lat - c.downtown_lat, lng - c.downtown_lng)

    return min(CITIES.values(), key=dist)
