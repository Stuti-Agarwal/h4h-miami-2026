"""Deterministic sanity/regression checks for app/scoring.py (no network)."""
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pytest
from shapely import Polygon

from app.scoring import Scorer, load_routes

MIAMI = ZoneInfo("America/New_York")


def at(hour):
    return datetime(2026, 10, 10, hour, 0, tzinfo=MIAMI)


@pytest.fixture(scope="module")
def scorer():
    return Scorer()


@pytest.fixture(scope="module")
def routes():
    return load_routes()


@pytest.fixture(scope="module")
def synthetic():
    """A Scorer whose only building is a 20x20 m, 30 m tall box."""
    s = Scorer.__new__(Scorer)
    s.buildings = [(Polygon([(1000, 1000), (1020, 1000), (1020, 1020), (1000, 1020)]), 30.0)]
    return s


def shadow_offset(s, hour):
    """(dx, dy, bearing_deg) from building centroid to shadow centroid."""
    tree = s.shadows(at(hour))
    c = tree.geometries[0].centroid
    dx, dy = c.x - 1010, c.y - 1010
    return dx, dy, math.degrees(math.atan2(dx, dy)) % 360


def test_shadow_points_west_in_morning(synthetic):
    dx, dy, bearing = shadow_offset(synthetic, 9)
    assert dx < 0 and 225 < bearing < 315, bearing


def test_shadow_points_north_near_midday(synthetic):
    dx, dy, bearing = shadow_offset(synthetic, 13)
    assert dy > 0 and (bearing > 315 or bearing < 45), bearing


def test_shadow_points_east_in_afternoon(synthetic):
    dx, dy, bearing = shadow_offset(synthetic, 17)
    assert dx > 0 and 45 < bearing < 135, bearing


def test_no_shadows_at_night(synthetic):
    assert synthetic.shadows(at(23)) is None


def test_shadow_shrinks_as_sun_rises(synthetic):
    area = {h: synthetic.shadows(at(h)).geometries[0].area for h in (9, 13)}
    assert area[9] > area[13]


def test_night_has_no_daylight_or_shade(scorer, routes):
    for r in routes.values():
        m = scorer.score(r["geometry"]["coordinates"], at(21))
        assert m["daylight"] is False
        assert m["shade"] == m["building_shade"] == m["tree_shade"] == 0


def rank(scorer, routes, when):
    """Mirrors _rank in app/server.py."""
    scored = [{"name": n, **scorer.score(r["geometry"]["coordinates"], when)} for n, r in routes.items()]
    base = "sun_exposed_m" if scored[0]["daylight"] else "longest_dark_m"
    return sorted(scored, key=lambda r: r[base] + 4 * r["under_highway_m"])


@pytest.mark.parametrize("hour,best", [(9, "NW 2nd Ave"), (13, "NW 2nd Ave"), (16, "NW 2nd Ave"), (21, "N Miami Ave")])
def test_ranking_regression(scorer, routes, hour, best):
    assert rank(scorer, routes, at(hour))[0]["name"] == best


@pytest.mark.parametrize("hour", [9, 13, 16, 21])
def test_metric_bounds(scorer, routes, hour):
    for r in rank(scorer, routes, at(hour)):
        for k in ("shade", "building_shade", "tree_shade", "lit", "active", "transit"):
            assert 0 <= r[k] <= 1, (r["name"], k, r[k])
        assert r["shade"] >= max(r["building_shade"], r["tree_shade"])
        assert 0 <= r["sun_exposed_m"] <= r["distance_m"]
        assert 0 <= r["longest_dark_m"] <= r["distance_m"] + 10


def test_landcover_has_tree_and_water(scorer):
    codes = set(np.unique(scorer.landcover).tolist())
    assert 6 in codes and 8 in codes, codes
