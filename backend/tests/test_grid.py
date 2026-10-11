"""H3 grid generation tests."""

from __future__ import annotations

import h3
from app.etl.grid import (
    cell_polygon_coords,
    fallback_boundary,
    generate_grid,
    haversine_km,
)
from shapely.geometry import Point


def test_fallback_boundary_covers_quebec(settings):
    poly = fallback_boundary(settings)
    assert poly.contains(Point(-71.2075, 46.8131))


def test_generate_grid_res8(settings):
    cells = generate_grid(fallback_boundary(settings), 8)
    assert len(cells) > 100
    assert all(h3.is_valid_cell(c) for c in cells)
    assert all(h3.get_resolution(c) == 8 for c in cells)
    assert cells == sorted(cells)


def test_cell_polygon_ring_is_closed(settings):
    cell = generate_grid(fallback_boundary(settings), 8)[0]
    ring = cell_polygon_coords(cell)
    assert ring[0] == ring[-1]
    assert len(ring) >= 7  # hexagon + closing point


def test_haversine_known_distance():
    # Québec City -> Montréal ~ 233 km
    d = haversine_km(46.8131, -71.2075, 45.5019, -73.5674)
    assert 220 < d < 250
