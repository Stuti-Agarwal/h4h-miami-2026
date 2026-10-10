"""Flask app: serves the map page, scores walking routes for a chosen time, and answers route questions with Gemma."""
import math
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from shapely import LineString, unary_union

load_dotenv()

from app.gemma import chat, summarize  # noqa: E402
from app.routing import candidates, geocode, in_bbox, suggest  # noqa: E402
from app.scoring import BBOX, M_PER_DEG_LAT, M_PER_DEG_LON, Scorer, load_routes, search_places, to_m  # noqa: E402

INCIDENT_W = 20  # routes run 25-64/km; +5/km = 100 m flips a close call, a ~900 m shade lead survives 2x the rate
GOALS = ("auto", "busy")
MIAMI = ZoneInfo("America/New_York")
LANGS = ("English", "Spanish", "Haitian Creole")
app = Flask(__name__, static_folder="static")
scorer = Scorer()
demo_routes = load_routes()  # cached 300 SW 2nd Ave -> The LAB Miami, used when no points are given or routing fails


class BadRequest(ValueError):
    pass


@app.errorhandler(BadRequest)
def bad_request(e):
    return jsonify({"error": str(e)}), 400


def _when(args):
    try:
        d = date.fromisoformat(args.get("date", "2026-10-10"))
        hour = min(max(float(args.get("hour", 16)), 0), 23.75)
    except ValueError as e:
        raise BadRequest("Invalid date or hour") from e
    return datetime.combine(d, time(int(hour), int(round(hour % 1 * 60)) % 60), MIAMI)


def _point(text):
    try:
        lon, lat = (float(v) for v in text.split(","))
    except ValueError as e:
        raise BadRequest("Points must be 'lon,lat'") from e
    if not in_bbox(lon, lat):
        raise BadRequest("We only have shade and lighting data for Downtown to Wynwood so far.")
    return round(lon, 5), round(lat, 5)


def _routes(args):
    if not (args.get("from") and args.get("to")):
        return demo_routes
    found = candidates(_point(args["from"]), _point(args["to"]))
    if not found:
        raise BadRequest("Couldn't find a walking route between those points.")
    return found


def _goal(args):
    goal = args.get("goal", "auto")
    return goal if goal in GOALS else "auto"


def _key(r, goal, base):
    """Sort key, lower is better. auto: 1 m under an elevated highway weighs like 4 m of sun (day) or of dark
    stretch (night); 1 reported incident against people per km weighs like INCIDENT_W m of sun / dark stretch.
    busy: 1 storefront/km and 1000 cars/day each = 10 points = 2.5 m under a highway. Demo routes span 28-35
    storefronts/km (~60 pts) and 8.3k-12.5k cars/day (~40 pts); at aadt/1000 traffic spanned only 4 pts and never
    mattered. Same highway and incident penalties."""
    penalty = 4 * r["under_highway_m"] + INCIDENT_W * r["incidents_per_km"]
    if goal == "busy":
        return -(r["storefronts_per_km"] * 10 + r["traffic_aadt"] / 100) + penalty
    return r[base] + penalty


def _rank(args):
    when, goal = _when(args), _goal(args)
    scored = [{"name": n, "geometry": r["geometry"], **scorer.score(r["geometry"]["coordinates"], when)}
              for n, r in _routes(args).items()]
    day = scored[0]["daylight"]
    base = "sun_exposed_m" if day else "longest_dark_m"
    scored.sort(key=lambda r: _key(r, goal, base))
    return {"when": when.strftime("%A %b %d, %I:%M %p"), "daylight": day, "goal": goal,
            "recommended": scored[0]["name"], "routes": scored}


def _lang(args):
    lang = args.get("lang", "English")
    return lang if lang in LANGS else "English"


def _to_lonlat(x, y):
    return [round(x / M_PER_DEG_LON + BBOX[0], 5), round(y / M_PER_DEG_LAT + BBOX[1], 5)]


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/routes")
def score_routes():
    return jsonify(_rank(request.args))


@app.get("/api/summary")
def summary():
    return jsonify(summarize(_rank(request.args), _lang(request.args)))


@app.post("/api/chat")
def ask():
    body = request.get_json(silent=True) or {}
    question = str(body.get("question", "")).strip()[:500]
    if not question:
        raise BadRequest("Ask a question about your walk.")
    history = [m for m in body.get("history", [])[-6:] if isinstance(m, dict)]
    scored = _rank(body)
    best = next(r for r in scored["routes"] if r["name"] == scored["recommended"])
    day = _when(body).date()
    other_times = []
    for h in (8, 10, 12, 14, 16, 18, 20, 22):
        s = scorer.score(best["geometry"]["coordinates"], datetime.combine(day, time(h), MIAMI))
        other_times.append(f"{h:02d}:00 " + (f"{s['sun_exposed_m']} m in direct sun" if s["daylight"]
                                             else f"dark (longest unlit, empty stretch {s['longest_dark_m']} m)"))
    return jsonify(chat(scored, question, history, _lang(body), "; ".join(other_times)))


@app.get("/api/geocode")
def search():
    q = request.args.get("q", "").strip()[:200]
    if not q:
        raise BadRequest("Type an address or place.")
    hit = geocode(q + ", Miami, FL")
    if not hit:
        raise BadRequest(f"Couldn't find '{q}' in Downtown–Wynwood.")
    return jsonify(hit)


@app.get("/api/suggest")
def suggestions():
    q = request.args.get("q", "").strip()[:80]
    if len(q) < 2:
        return jsonify([])
    # remote=0: local places only (~2 ms), so the page can show something before Photon answers.
    return jsonify(suggest(q, search_places(q), remote=request.args.get("remote") != "0"))


@app.get("/api/shadows")
def shadows():
    tree = scorer.shadows(_when(request.args))
    if tree is None:
        return jsonify({"type": "FeatureCollection", "features": []})
    # Only shadows near the routes on screen: the whole demo area is ~3.4 MB per slider move.
    near = unary_union([LineString([to_m(x, y) for x, y in r["geometry"]["coordinates"]]).buffer(80)
                        for r in _routes(request.args).values()])
    features = [{"type": "Feature", "properties": {},
                 "geometry": {"type": "Polygon",
                              "coordinates": [[_to_lonlat(x, y) for x, y in p.simplify(2).exterior.coords]]}}
                for p in tree.geometries[tree.query(near, predicate="intersects")]
                if not math.isnan(p.area) and p.area > 0]
    return jsonify({"type": "FeatureCollection", "features": features})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
