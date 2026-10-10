"""Fetch camera locations and recent reported crime incidents for the demo bbox.

Sources (all public, key-less):
  cameras   - Miami-Dade County "Traffic Cameras" ArcGIS FeatureServer (FDOT D6 CCTV)
            - OpenStreetMap man_made=surveillance nodes via Overpass (ODbL)
  incidents - City of Miami Police "Crimes" ArcGIS FeatureServer (NIBRS, point-level)

Writes data/cameras.geojson and data/incidents.geojson. Run: python scripts/fetch_safety.py
"""
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

XMIN, YMIN, XMAX, YMAX = -80.212, 25.765, -80.184, 25.807
DATA = Path(__file__).resolve().parent.parent / "data"
UA = {"User-Agent": "SombraRoute-hackathon/1.0"}

MDC_CAMERAS = "https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/TrafficCameras/FeatureServer/0"
MIAMI_CRIMES = "https://services1.arcgis.com/CvuPhqcTQpZPT9qY/arcgis/rest/services/Crimes_public_67c0535145c14baf897e47a8d4986539/FeatureServer/0"
OVERPASS = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"


def arcgis_query(url, where="1=1", out_fields="*"):
    """Page through an ArcGIS layer restricted to the bbox; return GeoJSON features."""
    feats, offset = [], 0
    while True:
        r = requests.get(f"{url}/query", headers=UA, timeout=60, params={
            "where": where, "outFields": out_fields, "f": "geojson", "outSR": 4326,
            "geometry": f"{XMIN},{YMIN},{XMAX},{YMAX}", "geometryType": "esriGeometryEnvelope",
            "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
            "orderByFields": "OBJECTID ASC" if "Crimes" in url else "",
            "resultOffset": offset, "resultRecordCount": 2000,
        })
        r.raise_for_status()
        page = r.json().get("features", [])
        feats += page
        if len(page) < 2000:
            return feats
        offset += len(page)


def point(lon, lat, props):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props}


def fetch_cameras():
    out = []
    for f in arcgis_query(MDC_CAMERAS):
        lon, lat = f["geometry"]["coordinates"][:2]
        out.append(point(lon, lat, {"source": "miami-dade-traffic-cameras", "kind": "traffic_cctv",
                                    "name": f["properties"].get("DESCRIPT")}))
    q = f'[out:json][timeout:60];node["man_made"="surveillance"]({YMIN},{XMIN},{YMAX},{XMAX});out;'
    elements = None
    for attempt in range(4):  # public Overpass mirrors are flaky; retry, then skip OSM
        try:
            r = requests.post(OVERPASS, data={"data": q}, headers=UA, timeout=90)
            r.raise_for_status()
            elements = r.json()["elements"]
            break
        except (requests.RequestException, ValueError) as e:
            print(f"overpass attempt {attempt + 1} failed: {e}")
            time.sleep(5)
    if elements is None:
        print("WARNING: OSM cameras skipped (Overpass unavailable)")
    for e in elements or []:
        t = e.get("tags", {})
        out.append(point(e["lon"], e["lat"], {
            "source": "openstreetmap", "osm_id": e["id"], "kind": t.get("surveillance:type", "camera"),
            "surveillance": t.get("surveillance"), "operator": t.get("operator")}))
    return out


def fetch_incidents():
    since = datetime.now(timezone.utc) - timedelta(days=365)
    where = f"reportdate >= TIMESTAMP '{since:%Y-%m-%d %H:%M:%S}'"
    fields = "OBJECTID,nibrsoffense,nibrscrimeag,nibrsdesc,reportdate,fulladdr,neighborhood"
    out = []
    for f in arcgis_query(MIAMI_CRIMES, where=where, out_fields=fields):
        if not f.get("geometry"):
            continue
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"][:2]
        date = datetime.fromtimestamp(p["reportdate"] / 1000, timezone.utc).isoformat() if p.get("reportdate") else None
        out.append(point(lon, lat, {
            "source": "city-of-miami-police-crimes", "date": date,
            "offense": p.get("nibrsoffense"), "category": p.get("nibrscrimeag"),
            "desc": (p.get("nibrsdesc") or "").strip(), "address": p.get("fulladdr"),
            "neighborhood": p.get("neighborhood")}))
    return out


def save(name, feats):
    (DATA / name).write_text(json.dumps({"type": "FeatureCollection", "features": feats}))


if __name__ == "__main__":
    t = time.time()
    cams = fetch_cameras()
    save("cameras.geojson", cams)
    by_src = {}
    for c in cams:
        by_src[c["properties"]["source"]] = by_src.get(c["properties"]["source"], 0) + 1
    print(f"cameras: {len(cams)} {by_src}")
    inc = fetch_incidents()
    save("incidents.geojson", inc)
    dates = sorted(i["properties"]["date"] for i in inc if i["properties"]["date"])
    cats = {}
    for i in inc:
        cats[i["properties"]["category"]] = cats.get(i["properties"]["category"], 0) + 1
    print(f"incidents: {len(inc)} ({dates[0] if dates else '-'} .. {dates[-1] if dates else '-'}) {cats}")
    print(f"done in {time.time() - t:.1f}s")
