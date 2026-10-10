"""Download elevated highway segments (motorway/trunk bridges, OSM) for the demo area into data/highways.geojson."""
import json
import pathlib
import urllib.parse
import urllib.request

BBOX = (-80.212, 25.765, -80.184, 25.807)  # keep in sync with fetch_overture.py
DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
OVERPASS = "https://overpass-api.de/api/interpreter"


def main():
    s, w, n, e = BBOX[1], BBOX[0], BBOX[3], BBOX[2]
    query = (f'[out:json][timeout:90];way["highway"~"^(motorway|motorway_link|trunk|trunk_link)$"]["bridge"]'
             f'({s},{w},{n},{e});out geom tags;')
    req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": query}).encode(),
                                 headers={"User-Agent": "h4h-miami-2026/0.1"})
    with urllib.request.urlopen(req, timeout=150) as r:
        elements = json.load(r)["elements"]
    features = [{"type": "Feature",
                 "geometry": {"type": "LineString", "coordinates": [[p["lon"], p["lat"]] for p in el["geometry"]]},
                 "properties": {"name": el["tags"].get("ref") or el["tags"].get("name")}}
                for el in elements]
    (DATA / "highways.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    print("highways", len(features), sorted({f["properties"]["name"] or "?" for f in features}))


if __name__ == "__main__":
    main()
