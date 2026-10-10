"""Candidate walking routes between two points (FOSSGIS OSRM foot profile) and address search (Nominatim)."""
import math
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import requests
from shapely import LineString

from app.scoring import BBOX, to_m

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


@lru_cache(maxsize=64)
def candidates(start, end):
    """start/end: (lon, lat) tuples. Returns {name: {"distance_m", "geometry"}} with up to MAX_ROUTES distinct routes."""
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
