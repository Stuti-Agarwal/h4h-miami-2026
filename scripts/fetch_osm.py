"""Download OpenStreetMap street lamps and streets tagged lit=yes for the demo area into data/osm_lit.geojson."""
import json
import pathlib
import sys
import urllib.parse
import urllib.request

BBOX = (-80.212, 25.765, -80.184, 25.807)  # keep in sync with fetch_overture.py
DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
OVERPASS = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"  # overpass-api.de rejected requests on event day


def download():
    s, w, n, e = BBOX[1], BBOX[0], BBOX[3], BBOX[2]
    query = (f'[out:json][timeout:90];(node["highway"="street_lamp"]({s},{w},{n},{e});'
             f'way["highway"]["lit"="yes"]({s},{w},{n},{e}););out geom;')
    req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": query}).encode(),
                                 headers={"User-Agent": "h4h-miami-2026/0.1"})
    with urllib.request.urlopen(req, timeout=150) as r:
        return json.load(r)


def main():
    # Optional arg: a saved Overpass JSON response, for when the mirror is down.
    raw = json.loads(pathlib.Path(sys.argv[1]).read_text()) if len(sys.argv) > 1 else download()
    elements = raw["elements"]
    features = []
    for el in elements:
        if el["type"] == "node":
            geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
        else:
            geom = {"type": "LineString", "coordinates": [[p["lon"], p["lat"]] for p in el["geometry"]]}
        features.append({"type": "Feature", "geometry": geom, "properties": {}})
    (DATA / "osm_lit.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    print("osm_lit", len(features))


if __name__ == "__main__":
    main()
