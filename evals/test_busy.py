"""goal=busy: storefront + car-traffic ranking (no network)."""
from app.gemma import _route_lines
from app.scoring import _load
from app.server import _key, _rank


def test_traffic_loads():
    traffic = _load("traffic")
    assert traffic and all(f["properties"]["aadt"] > 0 for f in traffic)


def test_busy_payload():
    p = _rank({"hour": "16", "goal": "busy"})
    assert p["goal"] == "busy" and p["recommended"] in {r["name"] for r in p["routes"]}
    for r in p["routes"]:
        assert r["storefronts_per_km"] > 0 and isinstance(r["traffic_aadt"], int)
    assert "storefronts/mile" in _route_lines(p)


def test_night_ranks_busy():
    assert _rank({"hour": "21"})["goal"] == "busy"


def test_invalid_goal_is_auto():
    bad, auto = _rank({"hour": "16", "goal": "nope"}), _rank({"hour": "16"})
    assert bad["goal"] == auto["goal"] == "auto" and bad["recommended"] == auto["recommended"]


def _route(dark):
    return {"storefronts_per_km": 30, "traffic_aadt": 10000, "under_highway_m": 100, "incidents_per_km": 25,
            "longest_dark_m": dark, "sun_exposed_m": dark}


def test_night_busy_penalizes_dark_stretch():
    assert _key(_route(800), "busy", "longest_dark_m") > _key(_route(400), "busy", "longest_dark_m")


def test_day_busy_ignores_light():
    assert _key(_route(800), "busy", "sun_exposed_m") == _key(_route(400), "busy", "sun_exposed_m")
