"""Reported-incident density and safe stops (no network)."""
from collections import Counter

import pytest

from app.scoring import BBOX, MAX_SAFE_STOPS, Scorer, load_routes
from evals.test_highways import to_lonlat
from evals.test_scoring import at, rank


@pytest.fixture(scope="module")
def scorer():
    return Scorer()


def test_incidents_loaded(scorer):
    assert len(scorer.incidents.geometries) > 0


def test_route_through_dense_cluster_has_incidents(scorer):
    # Busiest geocoded block: a 60 m walk across it must pick up its reports.
    p = Counter((g.x, g.y) for g in scorer.incidents.geometries).most_common(1)[0][0]
    m = scorer.score([to_lonlat(p[0] - 30, p[1]), to_lonlat(p[0] + 30, p[1])], at(21))
    assert m["incidents_per_km"] > 0
    assert any(s["incident"] for s in m["samples"])


@pytest.mark.parametrize("hour", [16, 21])
def test_safe_stops_shape(scorer, hour):
    for r in load_routes().values():
        stops = scorer.score(r["geometry"]["coordinates"], at(hour))["safe_stops"]
        assert len(stops) <= MAX_SAFE_STOPS
        for s in stops:
            assert set(s) == {"name", "category", "lon", "lat"}
            assert BBOX[0] <= s["lon"] <= BBOX[2] and BBOX[1] <= s["lat"] <= BBOX[3]


@pytest.mark.parametrize("hour", [16, 21])
def test_ranking_has_winner_with_incidents(scorer, hour):
    ranked = rank(scorer, load_routes(), at(hour))
    assert len(ranked) == 4 and ranked[0]["name"]
    assert all("incidents_per_km" in r for r in ranked)
