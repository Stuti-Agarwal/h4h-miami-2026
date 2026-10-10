"""Storm awareness from the key-less National Weather Service API. Never raises: offline means no weather."""
import time
from datetime import datetime, timedelta

import requests

POINT = "25.786,-80.198"  # centre of the Downtown-Wynwood bbox
API = "https://api.weather.gov"
HEADERS = {"User-Agent": "SombraRoute (h4h-miami-2026)", "Accept": "application/geo+json"}
TTL, FAIL_TTL = 600, 60  # failures cached briefly so offline doesn't add 6 s to every request
_cache = {}  # name -> (expires_at, value)


def _get(url, **params):
    r = requests.get(url, params=params, headers=HEADERS, timeout=6)
    r.raise_for_status()
    return r.json()


def _cached(name, fetch):
    hit = _cache.get(name)
    if hit and hit[0] > time.time():
        return hit[1]
    try:
        value, ttl = fetch(), TTL
    except Exception:  # network, HTTP, JSON or shape errors: the app must work without weather
        value, ttl = [], FAIL_TTL
    _cache[name] = (time.time() + ttl, value)
    return value


def _alerts():
    return [{"event": p.get("event"), "severity": p.get("severity"), "headline": p.get("headline"),
             "ends": p.get("ends") or p.get("expires")}
            for p in (f["properties"] for f in _get(f"{API}/alerts/active", point=POINT)["features"])]


def _hourly():
    url = _get(f"{API}/points/{POINT}")["properties"]["forecastHourly"]
    return [{"start": p["startTime"], "rain_pct": int((p.get("probabilityOfPrecipitation") or {}).get("value") or 0),
             "thunder": "thunder" in (p.get("shortForecast") or "").lower(), "short": p.get("shortForecast") or ""}
            for p in _get(url)["properties"]["periods"]]


def alerts():
    """Active NWS alerts for the demo area: [{"event", "severity", "headline", "ends"}]."""
    return _cached("alerts", _alerts)


def hourly():
    """Hourly forecast (~7 days): [{"start" ISO, "rain_pct" int, "thunder" bool, "short"}]."""
    return _cached("hourly", _hourly)


def at(when):
    """The hourly period covering tz-aware datetime `when`, or None."""
    for p in hourly():
        start = datetime.fromisoformat(p["start"])
        if start <= when < start + timedelta(hours=1):
            return p
    return None
