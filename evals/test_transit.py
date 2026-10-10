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


def test_invalid_mode_is_walk():
    body = app.test_client().get("/api/routes?hour=16&mode=bus").get_json()
    assert body["mode"] == "walk" and all("legs" not in r for r in body["routes"])


def test_transit_mode_adds_metromover(monkeypatch):
    monkeypatch.setattr("app.routing._walk", lambda a, b: [list(a), list(b)])  # straight walk legs, no network
    body = app.test_client().get("/api/routes?hour=16&mode=transit").get_json()
    assert body["mode"] == "transit"
    names = [r["name"] for r in body["routes"]]
    assert "Metromover + walk" in names
    for r in body["routes"]:
        assert r["legs"] and {"sun_exposed_m", "longest_dark_m", "under_highway_m", "incidents_per_km"} <= r.keys()
        for leg in r["legs"]:
            assert {"type", "line", "from", "to", "distance_m", "geometry"} <= leg.keys()
    mover = next(r for r in body["routes"] if r["name"] == "Metromover + walk")
    ride = [leg for leg in mover["legs"] if leg["type"] == "transit"]
    assert len(ride) == 1 and ride[0]["distance_m"] >= 400 and ride[0]["line"].startswith("Metromover")


def test_walk_mode_unchanged():
    c = app.test_client()
    walk, default = c.get("/api/routes?hour=16&mode=walk").get_json(), c.get("/api/routes?hour=16").get_json()
    assert walk["mode"] == "walk" and walk["recommended"] == default["recommended"]
    assert [r["name"] for r in walk["routes"]] == [r["name"] for r in default["routes"]]
