"""/api/transit: nearest bus stops and Metromover/Metrorail stations at each end (no network)."""
from app.server import app

KEYS = {"name", "kind", "routes", "lon", "lat", "walk_m"}


def test_demo_transit():
    r = app.test_client().get("/api/transit")
    assert r.status_code == 200
    body = r.get_json()
    for side in ("board", "alight"):
        stops = body[side]
        assert 0 < len(stops) <= 3
        assert [s["walk_m"] for s in stops] == sorted(s["walk_m"] for s in stops)
        for s in stops:
            assert KEYS <= s.keys() and s["kind"] in {"bus", "metromover", "metrorail"} and s["walk_m"] <= 1000
    assert any(s["kind"] != "bus" for s in body["board"])  # Downtown start is near Metromover/Metrorail


def test_out_of_bbox():
    r = app.test_client().get("/api/transit?from=-80.3,25.7&to=-80.20199,25.80244")
    assert r.status_code == 400 and "error" in r.get_json()
