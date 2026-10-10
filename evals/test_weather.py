"""NWS storm awareness (no network: requests is faked)."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
import requests

from app import weather
from app.gemma import _weather as prompt_lines
from app.server import app

MIAMI = ZoneInfo("America/New_York")
ALERTS = {"features": [{"properties": {"event": "Flood Watch", "severity": "Moderate", "headline": "Flood Watch until 8 PM",
                                       "ends": None, "expires": "2026-10-10T20:00:00-04:00"}}]}
POINTS = {"properties": {"forecastHourly": "https://api.weather.gov/gridpoints/MFL/109,51/forecast/hourly"}}
HOURLY = {"properties": {"periods": [
    {"startTime": "2026-10-10T15:00:00-04:00", "probabilityOfPrecipitation": {"value": 20}, "shortForecast": "Partly Sunny"},
    {"startTime": "2026-10-10T16:00:00-04:00", "probabilityOfPrecipitation": {"value": 60},
     "shortForecast": "Chance Showers And Thunderstorms"},
    {"startTime": "2026-10-10T17:00:00-04:00", "probabilityOfPrecipitation": {"value": None}, "shortForecast": "Cloudy"},
]}}


class Resp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def fake_get(url, params=None, headers=None, timeout=None):
    assert "SombraRoute" in headers["User-Agent"] and timeout == 6
    return Resp(ALERTS if "alerts" in url else HOURLY if "hourly" in url else POINTS)


def down(*a, **k):
    raise requests.ConnectionError("offline")


@pytest.fixture(autouse=True)
def fresh_cache():
    weather._cache.clear()
    yield
    weather._cache.clear()


def test_alerts_parsed(monkeypatch):
    monkeypatch.setattr(weather.requests, "get", fake_get)
    assert weather.alerts() == [{"event": "Flood Watch", "severity": "Moderate", "headline": "Flood Watch until 8 PM",
                                 "ends": "2026-10-10T20:00:00-04:00"}]


def test_hourly_parsed(monkeypatch):
    monkeypatch.setattr(weather.requests, "get", fake_get)
    h = weather.hourly()
    assert [p["rain_pct"] for p in h] == [20, 60, 0]
    assert [p["thunder"] for p in h] == [False, True, False]
    assert h[1] == {"start": "2026-10-10T16:00:00-04:00", "rain_pct": 60, "thunder": True,
                    "short": "Chance Showers And Thunderstorms"}


def test_at_picks_period(monkeypatch):
    monkeypatch.setattr(weather.requests, "get", fake_get)
    assert weather.at(datetime(2026, 10, 10, 16, 30, tzinfo=MIAMI))["rain_pct"] == 60
    assert weather.at(datetime(2026, 10, 10, 17, 0, tzinfo=MIAMI))["short"] == "Cloudy"
    assert weather.at(datetime(2026, 10, 20, 12, 0, tzinfo=MIAMI)) is None


def test_cached(monkeypatch):
    monkeypatch.setattr(weather.requests, "get", fake_get)
    weather.alerts()
    monkeypatch.setattr(weather.requests, "get", down)
    assert weather.alerts()[0]["event"] == "Flood Watch"


def test_offline_returns_empty_and_routes_ok(monkeypatch):
    monkeypatch.setattr(weather.requests, "get", down)
    assert weather.alerts() == [] and weather.hourly() == [] and weather.at(datetime.now(MIAMI)) is None
    r = app.test_client().get("/api/routes?hour=16")
    assert r.status_code == 200 and r.get_json()["weather"] == {"alerts": [], "now": None}
    assert app.test_client().get("/api/weather").get_json() == {"alerts": [], "hourly": []}


def test_routes_weather_and_prompt(monkeypatch):
    monkeypatch.setattr(weather.requests, "get", fake_get)
    p = app.test_client().get("/api/routes?date=2026-10-10&hour=16").get_json()
    assert p["weather"]["now"] == {"rain_pct": 60, "thunder": True, "short": "Chance Showers And Thunderstorms"}
    text = prompt_lines(p)
    assert "Flood Watch until" in text and "60% chance of rain" in text and "covered transit" in text
    assert prompt_lines({}) == ""
