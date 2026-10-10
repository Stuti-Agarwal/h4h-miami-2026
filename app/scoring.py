"""Score walking routes for shade (day) and lit, active streets (night)."""
import json
import math
import os
import pathlib
import sqlite3
from datetime import datetime

import numpy as np
from PIL import Image
from shapely import STRtree, LineString, Point, Polygon, MultiPoint
from shapely.affinity import translate
from suncalc import get_position

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
DB = DATA / "sombra.db"  # built by scripts/build_sqlite.py
BBOX = (-80.212, 25.765, -80.184, 25.807)  # must match the bbox used by scripts/fetch_*.py
LAT0 = (BBOX[1] + BBOX[3]) / 2
M_PER_DEG_LON = 111_320 * math.cos(math.radians(LAT0))
M_PER_DEG_LAT = 110_540
TREE = 6
STEP_M = 10
LIT_M, LIT_WAY_M, ACTIVE_M, ACTIVE_MIN, TRANSIT_M = 30, 15, 50, 3, 100
MAX_SHADOW_M = 300
# Places likely open after dark; offices/services count only by day.
EVENING = {
    "restaurant", "fast_food_restaurant", "bar", "lounge", "nightlife_venue", "dance_club", "music_venue",
    "brewery", "cafe", "coffee_shop", "food_truck_stand", "food_court", "convenience_store",
    "food_and_beverage_store", "pharmacy_and_drug_store", "gas_station", "hotel", "lodging", "movie_theater",
}


def to_m(lon, lat):
    return (lon - BBOX[0]) * M_PER_DEG_LON, (lat - BBOX[1]) * M_PER_DEG_LAT


COLUMNS = {"buildings": ["height", "num_floors"], "places": ["name", "category", "confidence"], "lights": [], "stops": [], "osm_lit": []}


def _query(sqlite_sql, postgis_sql):
    """Rows from Supabase when SUPABASE_DB_URL is set, else from the local SQLite db.
    Each sql is a string or a (sql, params) tuple; params are always bound, never formatted in."""
    url = os.environ.get("SUPABASE_DB_URL")
    if url:
        import psycopg

        sql, params = postgis_sql if isinstance(postgis_sql, tuple) else (postgis_sql, ())
        with psycopg.connect(url) as conn:
            return conn.execute(sql, params).fetchall()
    sql, params = sqlite_sql if isinstance(sqlite_sql, tuple) else (sqlite_sql, ())
    with sqlite3.connect(DB) as conn:
        return conn.execute(sql, params).fetchall()


def _load(name):
    cols = "".join(", " + c for c in COLUMNS[name])
    rows = _query(f"select geom{cols} from {name}", f"select ST_AsGeoJSON(geom){cols} from {name}")
    return [{"geometry": json.loads(r[0]), "properties": dict(zip(COLUMNS[name], r[1:]))} for r in rows]


# Landmarks people navigate to rank above offices that happen to share a name.
_GOOD_CATEGORIES = ("park", "museum", "monument", "historic_site", "art_gallery", "arts_and_entertainment",
                    "performing_arts_venue", "theatre_venue", "music_venue", "event_venue", "festival_venue",
                    "stadium_arena", "public_plaza", "beach", "library", "train_station", "hotel", "lodging",
                    "restaurant", "casual_eatery", "cafe", "coffee_shop", "bar", "college_university",
                    "amusement_attraction", "movie_theater")
_OFFICE_CATEGORIES = ("technical_service", "real_estate_service", "professional_service", "financial_service",
                      "legal_service", "attorney_or_law_firm", "corporate_or_business_office",
                      "b2b_office_and_professional_service", "b2b_service", "home_service", "media_service",
                      "design_service", "building_or_construction_service")


def search_places(text, limit=4):
    """Named places matching every word of text, as (name, category, geojson, tier) rows.
    Tier 1 exact name, 2 name starts with text as whole word(s), 3 some word starts with text, 4 contains.
    A leading "The" in the name is ignored for tiers 1-2. Within a tier: landmarks, then others, then offices,
    then confidence. User text only ever goes in as bound parameters (LIKE wildcards escaped)."""
    q = " ".join(text.split())
    esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    words = [w.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") for w in q.split()] or [""]
    good, office = ",".join("?" * len(_GOOD_CATEGORIES)), ",".join("?" * len(_OFFICE_CATEGORIES))
    sql = ("select name, category, {geom}, case "
           "when lower(name) in (lower(?), lower(?)) then 1 "
           "when name {like} ? escape '\\' or name {like} ? escape '\\' then 2 "
           "when name {like} ? escape '\\' or name {like} ? escape '\\' then 3 else 4 end as tier "
           "from places where confidence >= 0.6 and "
           + " and ".join(["name {like} ? escape '\\'"] * len(words))
           + f" order by tier, case when category in ({good}) then 0 when category in ({office}) then 2 else 1 end, "
           "confidence desc limit ?")
    params = (q, "the " + q, esc + " %", "the " + esc + " %", esc + "%", "% " + esc + "%",
              *(f"%{w}%" for w in words), *_GOOD_CATEGORIES, *_OFFICE_CATEGORIES, limit * 4)
    rows = _query(
        (sql.format(geom="geom", like="like"), params),
        (sql.format(geom="ST_AsGeoJSON(geom)", like="ilike").replace("?", "%s"), params),
    )
    out, seen = [], set()
    for r in rows:  # one row per name (chains like Publix have many branches), so the slots show distinct places
        if r[0].lower() not in seen:
            seen.add(r[0].lower())
            out.append(r)
    return out[:limit]


def load_routes():
    rows = _query("select name, distance_m, geom from routes order by name",
                  "select name, distance_m, ST_AsGeoJSON(geom) from routes order by name")
    return {n: {"distance_m": d, "geometry": json.loads(g)} for n, d, g in rows}


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
        osm = _load("osm_lit")
        osm_lamps = [f for f in osm if f["geometry"]["type"] == "Point"]
        self.lights = STRtree(_points(_load("lights")) + _points(osm_lamps))
        self.lit_ways = STRtree([LineString([to_m(x, y) for x, y in f["geometry"]["coordinates"]])
                                 for f in osm if f["geometry"]["type"] == "LineString"])
        self.places = STRtree(_points(places))
        self.evening_places = STRtree(_points([f for f in places if f["properties"].get("category") in EVENING]))
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

        lit = [len(self.lights.query(p, predicate="dwithin", distance=LIT_M)) > 0
               or len(self.lit_ways.query(p, predicate="dwithin", distance=LIT_WAY_M)) > 0 for p in samples]
        places = self.places if shadows is not None else self.evening_places
        active = [len(places.query(p, predicate="dwithin", distance=ACTIVE_M)) >= ACTIVE_MIN for p in samples]
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
            "sun_exposed_m": round(line.length * (1 - frac(shaded))),
            "lit": frac(lit),  # county lights + OSM lamps and lit=yes streets; still incomplete
            "active": frac(active),
            "transit": frac(transit),
            "longest_dark_m": longest_dark * STEP_M,
            "samples": [{"lon": round(x, 6), "lat": round(y, 6), "shaded": s, "lit": l, "active": a}
                        for (x, y), s, l, a in zip(lonlat, shaded, lit, active)],
        }
