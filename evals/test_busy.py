"""goal=busy: storefront + car-traffic ranking (no network)."""
from app.gemma import _route_lines
from app.scoring import _load
from app.server import _rank


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
