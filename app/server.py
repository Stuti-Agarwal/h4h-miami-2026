"""Flask app: serves the map page and scores the cached demo routes for a chosen time."""
import json
import math
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request, send_from_directory

from app.scoring import BBOX, DATA, M_PER_DEG_LAT, M_PER_DEG_LON, Scorer

MIAMI = ZoneInfo("America/New_York")
app = Flask(__name__, static_folder="static")
scorer = Scorer()
routes = json.loads((DATA / "routes.json").read_text())


def _when():
    d = date.fromisoformat(request.args.get("date", "2026-10-10"))
    hour = min(max(float(request.args.get("hour", 16)), 0), 23.75)
    return datetime.combine(d, time(int(hour), int(round(hour % 1 * 60)) % 60), MIAMI)


def _to_lonlat(x, y):
    return [round(x / M_PER_DEG_LON + BBOX[0], 6), round(y / M_PER_DEG_LAT + BBOX[1], 6)]


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/routes")
def score_routes():
    when = _when()
    scored = [{"name": n, "geometry": r["geometry"], **scorer.score(r["geometry"]["coordinates"], when)}
              for n, r in routes.items()]
    day = scored[0]["daylight"]
    key = (lambda r: r["sun_exposed_m"]) if day else (lambda r: r["longest_dark_m"])
    scored.sort(key=key)
    return jsonify({"when": when.isoformat(), "daylight": day, "recommended": scored[0]["name"], "routes": scored})


@app.get("/api/shadows")
def shadows():
    tree = scorer.shadows(_when())
    if tree is None:
        return jsonify({"type": "FeatureCollection", "features": []})
    features = [{"type": "Feature", "properties": {},
                 "geometry": {"type": "Polygon",
                              "coordinates": [[_to_lonlat(x, y) for x, y in p.simplify(1).exterior.coords]]}}
                for p in tree.geometries if not math.isnan(p.area) and p.area > 0]
    return jsonify({"type": "FeatureCollection", "features": features})


if __name__ == "__main__":
    app.run(port=5050, debug=True)
