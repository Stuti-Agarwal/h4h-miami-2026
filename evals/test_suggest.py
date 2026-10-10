"""Deterministic ranking checks for scoring.search_places against the local SQLite db (no network)."""
import sqlite3

import pytest

from app.scoring import DB, search_places


@pytest.fixture(autouse=True)
def local_db(monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)


def names(q):
    return [r[0] for r in search_places(q)]


def test_lab_surfaces_the_lab_miami():
    assert "The LAB Miami" in names("lab")[:3]


@pytest.mark.parametrize("q", ["the lab", "lab miami", "The LAB Miami"])
def test_lab_variants_rank_venue_first(q):
    assert names(q)[0] == "The LAB Miami"


def test_multi_word_matches_all_words():
    got = names("wynwood walls")
    assert got and got[0].startswith("Wynwood Walls")
    assert all("wynwood" in n.lower() and "walls" in n.lower() for n in got)


def test_bayfront_park():
    assert "Bayfront Park" in names("bayfront")


def test_rows_carry_tier_and_names_are_distinct():
    rows = search_places("publix")
    assert rows and all(len(r) == 4 and r[3] in (1, 2, 3, 4) for r in rows)
    assert len({r[0].lower() for r in rows}) == len(rows)


@pytest.mark.parametrize("q", ["'; drop table places; --", "%", "_", "\\", "\" or 1=1 --"])
def test_injection_like_input_is_inert(q):
    assert isinstance(search_places(q), list)
    with sqlite3.connect(DB) as conn:
        assert conn.execute("select count(*) from places").fetchone()[0] > 0


def test_wildcards_are_literal():
    assert all("%" in n for n in names("%"))  # '%' matches only names containing a literal '%'
    assert all("_" in n for n in names("_"))
