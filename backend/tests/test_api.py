"""End-to-end API tests (offline pipeline + FastAPI TestClient)."""

from __future__ import annotations

from app.core.constants import FEATURES


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert 8 in body["resolutions"]
    assert body["zones_loaded"]["8"] > 100


def test_zones_geojson_structure(client):
    body = client.get("/api/zones", params={"resolution": 8}).json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) > 100
    feature = body["features"][0]
    assert feature["geometry"]["type"] == "Polygon"
    props = feature["properties"]
    assert 0 <= props["safety_score"] <= 100
    assert 0 <= props["calmness_score"] <= 100
    assert isinstance(props["profile"], str)


def test_zone_detail_and_404(client):
    cell = client.get("/api/zones", params={"resolution": 8}).json()["features"][0]["id"]
    detail = client.get(f"/api/zones/{cell}").json()
    assert detail["h3"] == cell
    assert detail["resolution"] == 8
    assert set(detail["counts"]) == set(FEATURES)
    assert client.get("/api/zones/not_a_cell").status_code == 404


def test_stats(client):
    body = client.get("/api/stats", params={"resolution": 8}).json()
    assert body["zone_count"] > 100
    assert 0 <= body["safety_mean"] <= 100
    assert body["safety_p10"] <= body["safety_p90"]
    assert sum(body["profiles"].values()) == body["zone_count"]


def test_unknown_resolution_404(client):
    assert client.get("/api/zones", params={"resolution": 5}).status_code == 404


def test_weights_endpoint(client):
    body = client.get("/api/weights").json()
    assert set(body["features"]) == set(FEATURES)
    assert "bar_nightlife" in body["safety_weights"]


def test_simulation_changes_scores(client):
    baseline = {
        f["id"]: f["properties"]["safety_score"]
        for f in client.get("/api/zones", params={"resolution": 8}).json()["features"]
    }
    payload = {"resolution": 8, "safety_weights": {"bar_nightlife": 0.5, "streetlight": -0.5}}
    body = client.post("/api/simulate", json=payload).json()
    assert body["applied_safety_weights"]["bar_nightlife"] == 0.5
    simulated = {z["h3"]: z["safety_score"] for z in body["zones"]}
    assert set(simulated) == set(baseline)
    assert any(abs(simulated[c] - baseline[c]) > 1 for c in baseline)


def test_simulation_rejects_unknown_feature(client):
    payload = {"resolution": 8, "safety_weights": {"dragons": 1.0}}
    assert client.post("/api/simulate", json=payload).status_code == 422


def test_index_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "ZoneScore" in response.text


def test_gzip_compression(client):
    response = client.get(
        "/api/zones", params={"resolution": 8}, headers={"Accept-Encoding": "gzip"}
    )
    assert response.status_code == 200
    assert response.headers.get("content-encoding") == "gzip"


def test_scaled_frame_cached():
    from app.api.store import get_store

    store = get_store()
    scaled = store.scaled_frame(8)
    assert not scaled.empty
    assert set(scaled.columns) == set(FEATURES)


def test_locate_endpoint(client):
    res = client.get("/api/locate", params={"lat": 46.8131, "lng": -71.2075, "resolution": 8})
    assert res.status_code == 200
    data = res.json()
    assert data["found"] is True
    assert "h3" in data
    assert "detail" in data
    assert "safety_score" in data["detail"]
    assert "family_score" in data["detail"]


def test_family_score_in_geojson_and_weights(client):
    geo = client.get("/api/zones", params={"resolution": 8}).json()
    assert "family_score" in geo["features"][0]["properties"]
    assert 0 <= geo["features"][0]["properties"]["family_score"] <= 100

    w = client.get("/api/weights").json()
    assert "family_weights" in w
    assert "school" in w["family_weights"]


def test_cities_endpoint(client):
    cities = client.get("/api/cities").json()
    assert isinstance(cities, list)
    assert len(cities) >= 4
    city_ids = [c["id"] for c in cities]
    assert "quebec" in city_ids
    assert "montreal" in city_ids
    assert "toronto" in city_ids
    assert "ottawa" in city_ids


def test_multi_city_zones_and_locate(client):
    # Test Montreal zones
    mtl = client.get("/api/zones", params={"city": "montreal", "resolution": 8}).json()
    assert mtl["type"] == "FeatureCollection"
    assert len(mtl["features"]) > 50

    # Test auto-city location detection for Montreal downtown
    loc_params = {"lat": 45.5017, "lng": -73.5673, "resolution": 8}
    loc = client.get("/api/locate", params=loc_params).json()
    assert loc["found"] is True
    assert loc["city"] == "montreal"
