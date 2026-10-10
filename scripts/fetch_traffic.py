"""Download FDOT Annual Average Daily Traffic road segments for the demo area into data/traffic.geojson."""
import json
import pathlib

import requests

BBOX = (-80.212, 25.765, -80.184, 25.807)  # keep in sync with fetch_overture.py
DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
URL = ("https://services1.arcgis.com/O1JpcwDW8sjYuddV/arcgis/rest/services/"
       "Annual_Average_Daily_Traffic_TDA/FeatureServer/0/query")
# FDOT roadway IDs of limited-access expressways: I-95, I-395/SR 836 and the MacArthur Causeway bridges.
# They carry cars over or past pedestrians, not along a sidewalk (walking under them is scored separately).
EXPRESSWAY = {"87270000", "87200000", "87060000"}


def main():
    features, offset = [], 0
    while True:
        r = requests.get(URL, params={
            "where": "1=1", "geometry": ",".join(map(str, BBOX)), "geometryType": "esriGeometryEnvelope",
            "inSR": 4326, "outSR": 4326, "spatialRel": "esriSpatialRelIntersects",
            "outFields": "AADT,ROADWAY,DESC_FRM,DESC_TO,YEAR_", "resultOffset": offset, "resultRecordCount": 1000,
            "f": "geojson"}, timeout=60)
        r.raise_for_status()
        page = r.json()["features"]
        features += page
        if len(page) < 1000:
            break
        offset += len(page)
    out = []
    for f in features:
        p, g = f["properties"], f["geometry"]
        desc = f"{p.get('DESC_FRM') or ''} / {p.get('DESC_TO') or ''}".strip(" /")
        if not g or not p.get("AADT") or p.get("ROADWAY") in EXPRESSWAY:
            continue
        lines = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
        for coords in lines:
            out.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords},
                        "properties": {"aadt": int(p["AADT"]), "road": f"{p['ROADWAY']} {desc}".strip()}})
    (DATA / "traffic.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": out}))
    print("traffic", len(features), "segments ->", len(out), "lines")


if __name__ == "__main__":
    main()
