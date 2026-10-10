"""Candidate walking routes (FOSSGIS OSRM foot profile), address search (Nominatim) and type-ahead suggestions (Photon)."""
import json
import math
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import requests
from shapely import LineString, Point
from shapely.ops import substring

from app.scoring import BBOX, DATA, to_m

OSRM = "https://routing.openstreetmap.de/routed-foot/route/v1/foot/"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "h4h-miami-2026/0.1 (hackathon demo)"}
VIA_OFFSETS_M = (-500, -250, 250, 500)  # sideways detours at the trip midpoint, to force distinct corridors
MAX_ROUTES = 4


def in_bbox(lon, lat):
    return BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]


def _osrm(points):
    url = OSRM + ";".join(f"{x:.6f},{y:.6f}" for x, y in points)
    r = requests.get(url, params={"overview": "full", "geometries": "geojson", "steps": "true",
                                  "alternatives": "true" if len(points) == 2 else "false"},
                     headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json().get("routes", [])


def _streets(route):
    """Street names on the route, longest stretch first."""
    lengths = {}
    for leg in route["legs"]:
        for s in leg["steps"]:
            if s.get("name"):
                lengths[s["name"]] = lengths.get(s["name"], 0) + s["distance"]
    return sorted(lengths, key=lengths.get, reverse=True)


def _abbrev(name):
    for long, short in (("Northwest", "NW"), ("Northeast", "NE"), ("Southwest", "SW"), ("Southeast", "SE"),
                        ("Avenue", "Ave"), ("Street", "St"), ("Boulevard", "Blvd"), ("North ", "N "), ("South ", "S ")):
        name = name.replace(long, short)
    return name


_found = {}  # successful results only: a transient OSRM failure must not be cached as "no route"


def candidates(start, end):
    """start/end: (lon, lat) tuples. Returns {name: {"distance_m", "geometry"}} with up to MAX_ROUTES distinct routes."""
    if (start, end) not in _found:
        kept = _candidates(start, end)
        if not kept:
            return kept
        _found[(start, end)] = kept
    return _found[(start, end)]


def _candidates(start, end):
    (x0, y0), (x1, y1) = to_m(*start), to_m(*end)
    length = math.hypot(x1 - x0, y1 - y0) or 1
    nx, ny = -(y1 - y0) / length, (x1 - x0) / length  # unit normal to the trip
    mid_lon, mid_lat = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
    m_lon, m_lat = to_m(1 + BBOX[0], 1 + BBOX[1])  # metres per degree
    vias = [(mid_lon + nx * d / m_lon, mid_lat + ny * d / m_lat) for d in VIA_OFFSETS_M]

    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs = [pool.submit(_osrm, [start, end])] + [pool.submit(_osrm, [start, v, end]) for v in vias]
        found = []
        for job in jobs:
            try:
                found += job.result()
            except requests.RequestException:
                continue

    kept, lines = {}, []
    for route in sorted(found, key=lambda r: r["distance"]):
        line = LineString([to_m(x, y) for x, y in route["geometry"]["coordinates"]])
        if any(line.buffer(25).intersection(other).length > 0.8 * other.length or
               other.buffer(25).intersection(line).length > 0.8 * line.length for other in lines):
            continue  # near-duplicate of a shorter route
        if route["distance"] > 1.6 * min(r["distance"] for r in found):
            continue  # too long a detour to be worth suggesting
        names = ["via " + _abbrev(s) for s in _streets(route)]
        name = next((n for n in names if n not in kept), None) or f"{names[0] if names else 'Route'} ({route['distance'] / 1000:.1f} km)"
        kept[name] = {"distance_m": round(route["distance"]), "geometry": route["geometry"]}
        lines.append(line)
        if len(kept) == MAX_ROUTES:
            break
    return kept


@lru_cache(maxsize=256)
def geocode(query):
    r = requests.get(NOMINATIM, params={"q": query, "format": "json", "limit": 1, "bounded": 1,
                                        "viewbox": f"{BBOX[0]},{BBOX[3]},{BBOX[2]},{BBOX[1]}"},
                     headers=HEADERS, timeout=10)
    r.raise_for_status()
    hits = r.json()
    if not hits:
        return None
    return {"lon": float(hits[0]["lon"]), "lat": float(hits[0]["lat"]), "label": hits[0]["display_name"].split(", Miami")[0]}


PHOTON = "https://photon.komoot.io/api/"


def _photon_label(p):
    street = " ".join(x for x in (p.get("housenumber"), p.get("street")) if x)
    return _abbrev(p.get("name") or street), _abbrev(street if p.get("name") else (p.get("district") or p.get("city") or "Miami"))


@lru_cache(maxsize=512)
def _photon(query):
    """Photon address hits for query (cached: the public API takes 0.6-2 s, too slow to wait on per keystroke)."""
    r = requests.get(PHOTON, params={"q": query, "limit": 6, "bbox": ",".join(map(str, BBOX))}, headers=HEADERS, timeout=3)
    r.raise_for_status()
    hits = []
    for f in r.json()["features"]:
        lon, lat = f["geometry"]["coordinates"][:2]
        label, detail = _photon_label(f["properties"])
        if label and label.strip() and in_bbox(lon, lat):
            hits.append({"label": label.strip(), "detail": detail, "lon": lon, "lat": lat})
    return tuple(hits)


def suggest(query, local_places, remote=True):
    """Up to 6 {label, detail, lon, lat}: strong local name matches first (instant, in-area), then Photon addresses.
    local_places: (name, category, geojson, tier) rows from scoring.search_places. Weak local 'contains' matches
    (tier 4) go last, and also below Photon for address-like queries (starting with a digit, e.g. "300 SW 2nd")."""
    strong, weak = [], []
    for name, category, geom, tier in local_places:
        lon, lat = json.loads(geom)["coordinates"][:2]
        (strong if tier <= 3 else weak).append(
            {"label": name, "detail": (category or "place").replace("_", " "), "lon": lon, "lat": lat})
    photon = []
    if remote:
        try:
            photon = [dict(h) for h in _photon(" ".join(query.lower().split()))]
        except (requests.RequestException, KeyError, ValueError):
            pass  # local suggestions still work offline
    qn = " ".join(query.lower().split())
    photon.sort(key=lambda s: not s["label"].lower().startswith(qn))  # e.g. "300 SW 2nd Ave" before "300 NE 2nd Ave"
    ordered = strong + (photon + weak if query.strip()[:1].isdigit() else weak + photon)
    out, seen = [], set()
    for s in ordered:
        key = " ".join(s["label"].lower().split())
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out[:6]


TRANSIT_MAX_M = 800
DETOUR = 1.25  # straight-line -> walking distance


@lru_cache(maxsize=1)
def _transit_stops():
    """Metromover/Metrorail stations (Miami-Dade open data, data/stations.geojson) + bus stops (data/stops.geojson)."""
    stops = [{**f["properties"], "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1]}
             for f in json.loads((DATA / "stations.geojson").read_text())["features"]]
    for f in json.loads((DATA / "stops.geojson").read_text())["features"]:
        x, y = f["geometry"]["coordinates"][:2]
        stops.append({"name": f["properties"].get("StopName") or "Bus stop", "kind": "bus", "routes": "",
                      "lon": round(x, 6), "lat": round(y, 6)})
    return stops


def nearest_transit(lon, lat, n=3):
    """Up to n stops within TRANSIT_MAX_M straight-line of (lon, lat), sorted by walk_m; keeps the nearest
    rail/mover station in the list if one is in range."""
    px, py = to_m(lon, lat)
    near = []
    for s in _transit_stops():
        x, y = to_m(s["lon"], s["lat"])
        d = math.hypot(x - px, y - py)
        if d <= TRANSIT_MAX_M:
            near.append({**s, "walk_m": round(d * DETOUR)})
    near.sort(key=lambda s: s["walk_m"])
    seen = set()  # bus stops come in pairs (one per side of the street); keep the nearer of each name
    near = [s for s in near if not ((s["name"], s["kind"]) in seen or seen.add((s["name"], s["kind"])))]
    top = near[:n]
    station = next((s for s in near if s["kind"] != "bus"), None)
    if station and station not in top and top:
        top[-1] = station
    return top


MIN_RIDE_M = 400


@lru_cache(maxsize=1)
def _mover_lines():
    """Metromover loops from data/transit.geojson (scripts/fetch_transit.py): [(name, metric LineString, closed,
    [(stop name, distance along line), ...] in service order)]."""
    feats = json.loads((DATA / "transit.geojson").read_text())["features"]
    out = []
    for f in feats:
        p = f["properties"]
        if f["geometry"]["type"] != "LineString" or p["kind"] != "metromover":
            continue
        line = LineString([to_m(x, y) for x, y in f["geometry"]["coordinates"]])
        stops, at = [], 0.0
        for s in sorted((s for s in feats if s["geometry"]["type"] == "Point" and s["properties"]["line"] == p["line"]),
                        key=lambda s: s["properties"]["order"]):
            # project onto the track past the previous stop, so out-and-back loops keep the stop sequence
            pt = Point(to_m(*s["geometry"]["coordinates"]))
            at += substring(line, at, line.length).project(pt)
            stops.append((s["properties"]["name"], at))
        out.append((p["line"], line, line.coords[0] == line.coords[-1], stops))
    return out


def _from_m(x, y):
    m_lon, m_lat = to_m(1 + BBOX[0], 1 + BBOX[1])
    return [round(x / m_lon + BBOX[0], 6), round(y / m_lat + BBOX[1], 6)]


@lru_cache(maxsize=128)
def _walk(a, b):
    """Shortest OSRM foot route a -> b as [[lon, lat], ...]; straight line if OSRM fails."""
    try:
        routes = _osrm([a, b])
        if routes:
            return routes[0]["geometry"]["coordinates"]
    except requests.RequestException:
        pass
    return [list(a), list(b)]


def _length(coords):
    return LineString([to_m(x, y) for x, y in coords]).length if len(coords) > 1 else 0.0


@lru_cache(maxsize=64)
def transit_option(start, end):
    """Walk -> Metromover -> walk from start to end ((lon, lat) tuples), or None if riding saves nothing.
    Picks the board/alight pair (in service order) with the least straight-line walking."""
    p0, p1 = to_m(*start), to_m(*end)
    best = None
    for name, line, closed, stops in _mover_lines():
        for i, (bn, ba) in enumerate(stops):
            for j, (an, aa) in enumerate(stops):
                if i == j or (j < i and not closed):
                    continue
                walk = math.dist(p0, line.interpolate(ba).coords[0]) + math.dist(line.interpolate(aa).coords[0], p1)
                if best is None or walk < best[0]:
                    best = (walk, name, line, bn, ba, an, aa)
    if best is None:
        return None
    walk, name, line, bn, ba, an, aa = best
    if ba <= aa:
        ride = list(substring(line, ba, aa).coords)
    else:  # closed loop: wrap past the end
        ride = list(substring(line, ba, line.length).coords) + list(substring(line, 0, aa).coords)[1:]
    ride_m = LineString(ride).length
    if bn == an or ride_m < MIN_RIDE_M or walk >= math.dist(p0, p1):
        return None
    ride = [_from_m(x, y) for x, y in ride]
    first, last = _walk(start, tuple(ride[0])), _walk(tuple(ride[-1]), end)
    legs = [{"type": "walk", "line": None, "from": None, "to": bn, "distance_m": round(_length(first)),
             "geometry": {"type": "LineString", "coordinates": first}},
            {"type": "transit", "line": f"Metromover {name}", "from": bn, "to": an, "distance_m": round(ride_m),
             "geometry": {"type": "LineString", "coordinates": ride}},
            {"type": "walk", "line": None, "from": an, "to": None, "distance_m": round(_length(last)),
             "geometry": {"type": "LineString", "coordinates": last}}]
    return {"distance_m": sum(leg["distance_m"] for leg in legs), "legs": legs,
            "geometry": {"type": "LineString", "coordinates": first + ride + last}}
