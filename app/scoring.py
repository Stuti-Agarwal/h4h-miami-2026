"""Score walking routes for shade (day) and lit, active streets (night)."""
import json
import math
import pathlib
from datetime import datetime

import numpy as np
from PIL import Image
from shapely import STRtree, LineString, Point, Polygon, MultiPoint
from shapely.affinity import translate
from suncalc import get_position

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
BBOX = (-80.212, 25.765, -80.184, 25.807)  # must match the bbox used by scripts/fetch_*.py
LAT0 = (BBOX[1] + BBOX[3]) / 2
M_PER_DEG_LON = 111_320 * math.cos(math.radians(LAT0))
M_PER_DEG_LAT = 110_540
TREE = 6
STEP_M = 10
LIT_M, ACTIVE_M, ACTIVE_MIN, TRANSIT_M = 30, 50, 3, 100
MAX_SHADOW_M = 300


def to_m(lon, lat):
    return (lon - BBOX[0]) * M_PER_DEG_LON, (lat - BBOX[1]) * M_PER_DEG_LAT


def _load(name):
    return json.loads((DATA / f"{name}.geojson").read_text())["features"]


def _points(features):
    return [Point(to_m(*f["geometry"]["coordinates"][:2])) for f in features if f["geometry"]]


def _outer_rings(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    if geom["type"] == "MultiPolygon":
        return [p[0] for p in geom["coordinates"]]
    return []


def _height(props):
    if props.get("height"):
        return props["height"]
    if props.get("num_floors"):
        return props["num_floors"] * 3.5
    return 6.0  # unknown: assume ~2 floors


class Scorer:
    def __init__(self):
        self.buildings = [
            (Polygon([to_m(x, y) for x, y in ring]), _height(f["properties"]))
            for f in _load("buildings") for ring in _outer_rings(f["geometry"])
        ]
        places = [f for f in _load("places") if (f["properties"].get("confidence") or 0) >= 0.6]
        self.lights = STRtree(_points(_load("lights")))
        self.places = STRtree(_points(places))
        self.stops = STRtree(_points(_load("stops")))
        self.landcover = np.array(Image.open(DATA / "landcover.tif"))

    def shadows(self, when: datetime):
        """Building shadow polygons (metres) for a tz-aware datetime; empty when the sun is down."""
        sun = get_position(when, (BBOX[0] + BBOX[2]) / 2, LAT0)
        alt, az = sun["altitude"], sun["azimuth"]  # suncalc azimuth: from south, positive westward
        if alt <= 0:
            return None
        # Shadow points away from the sun; its compass bearing equals suncalc's azimuth.
        dx, dy = math.sin(az), math.cos(az)
        polys = []
        for poly, h in self.buildings:
            length = min(h / math.tan(alt), MAX_SHADOW_M)
            moved = translate(poly, dx * length, dy * length)
            polys.append(MultiPoint(list(poly.exterior.coords) + list(moved.exterior.coords)).convex_hull)
        return STRtree(polys)

    def _tree(self, lon, lat):
        h, w = self.landcover.shape
        col = int((lon - BBOX[0]) / (BBOX[2] - BBOX[0]) * w)
        row = int((BBOX[3] - lat) / (BBOX[3] - BBOX[1]) * h)
        window = self.landcover[max(row - 1, 0):row + 2, max(col - 1, 0):col + 2]  # ~3 m around the sidewalk
        return bool((window == TREE).any())

    def score(self, coords, when: datetime):
        """coords: [[lon, lat], ...] route geometry. Returns per-route metrics."""
        line = LineString([to_m(x, y) for x, y in coords])
        n = max(int(line.length // STEP_M), 1)
        samples = [line.interpolate(i * STEP_M) for i in range(n + 1)]
        lonlat = [(p.x / M_PER_DEG_LON + BBOX[0], p.y / M_PER_DEG_LAT + BBOX[1]) for p in samples]

        shadows = self.shadows(when)
        if shadows is not None:
            in_bldg = [len(shadows.query(p, predicate="intersects")) > 0 for p in samples]
            in_tree = [self._tree(*ll) for ll in lonlat]
            shaded = [b or t for b, t in zip(in_bldg, in_tree)]
        else:
            in_bldg = in_tree = shaded = [False] * len(samples)

        lit = [len(self.lights.query(p, predicate="dwithin", distance=LIT_M)) > 0 for p in samples]
        active = [len(self.places.query(p, predicate="dwithin", distance=ACTIVE_M)) >= ACTIVE_MIN for p in samples]
        transit = [len(self.stops.query(p, predicate="dwithin", distance=TRANSIT_M)) > 0 for p in samples]

        dark, longest_dark = 0, 0
        for l, a in zip(lit, active):
            dark = 0 if (l or a) else dark + 1
            longest_dark = max(longest_dark, dark)

        frac = lambda xs: round(sum(xs) / len(xs), 3)
        return {
            "distance_m": round(line.length),
            "daylight": shadows is not None,
            "shade": frac(shaded),
            "building_shade": frac(in_bldg),
            "tree_shade": frac(in_tree),
            "lit": frac(lit),
            "active": frac(active),
            "transit": frac(transit),
            "longest_dark_m": longest_dark * STEP_M,
            "samples": [{"lon": round(x, 6), "lat": round(y, 6), "shaded": s, "lit": l, "active": a}
                        for (x, y), s, l, a in zip(lonlat, shaded, lit, active)],
        }
