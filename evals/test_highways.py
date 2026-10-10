"""Under-elevated-highway metric and its effect on ranking (no network)."""
import pytest

from app.scoring import BBOX, M_PER_DEG_LAT, M_PER_DEG_LON, Scorer, load_routes
from evals.test_scoring import at, rank


@pytest.fixture(scope="module")
def scorer():
    return Scorer()


def to_lonlat(x, y):
    return [x / M_PER_DEG_LON + BBOX[0], y / M_PER_DEG_LAT + BBOX[1]]


def test_highways_loaded(scorer):
    assert len(scorer.highways.geometries) > 0


def test_route_along_highway_is_under(scorer):
    hwy = max(scorer.highways.geometries, key=lambda g: g.length)
    coords = [to_lonlat(*hwy.interpolate(f, normalized=True).coords[0]) for f in (0, 0.25, 0.5, 0.75, 1)]
    m = scorer.score(coords, at(16))
    assert m["under_highway_m"] > 0
    assert any(s["under"] for s in m["samples"])


def test_route_far_from_highways_is_not_under(scorer):
    # Short walk in the bbox's NE corner (Biscayne Bay shore), well away from I-95/I-395/SR 836.
    coords = [[-80.1865, 25.8000], [-80.1865, 25.8040]]
    assert scorer.score(coords, at(16))["under_highway_m"] == 0


@pytest.mark.parametrize("hour", [16, 21])
def test_demo_ranking_has_winner(scorer, hour):
    ranked = rank(scorer, load_routes(), at(hour))
    assert len(ranked) == 4 and ranked[0]["name"]
