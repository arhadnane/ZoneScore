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
    baseline = {f["id"]: f["properties"]["safety_score"]
                for f in client.get("/api/zones", params={"resolution": 8}).json()["features"]}
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
    assert "URBISQC" in response.text
