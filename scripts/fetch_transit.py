"""Fetch Metromover loops + Metrorail Green Line (track + stops) from OSM Overpass -> data/transit.geojson.

Lines: one LineString per route relation, member ways chained in service order.
Stations: stop nodes as Points with name, line and order (stop sequence along the relation)."""
import json
from pathlib import Path

import requests

OVERPASS = ("https://overpass-api.de/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter")
HEADERS = {"User-Agent": "h4h-miami-2026/0.1 (hackathon demo)"}
RELATIONS = {1589483: "Omni Loop", 1589482: "Inner Loop", 1589481: "Brickell Loop", 4499117: "Metrorail Green"}
OUT = Path(__file__).resolve().parent.parent / "data" / "transit.geojson"
QUERY = f"""[out:json][timeout:90];
relation(id:{",".join(map(str, RELATIONS))})->.r;
.r out geom;
node(r.r);
out tags;"""


def fetch():
    for url in OVERPASS:
        try:
            r = requests.post(url, data={"data": QUERY}, headers=HEADERS, timeout=120)
            r.raise_for_status()
            return r.json()["elements"]
        except (requests.RequestException, ValueError) as e:
            print(f"{url}: {e}")
    raise SystemExit("all Overpass mirrors failed")


def chain(ways):
    """Join way coordinate lists end to end, flipping each so it continues from the previous one."""
    line = []
    for w in ways:
        if not line:
            line = list(w)
            continue
        ends = [(line[-1], w), (line[-1], w[::-1]), (line[0], w), (line[0], w[::-1])]
        d = [abs(a[0] - b[0][0]) + abs(a[1] - b[0][1]) for a, b in ends]
        i = d.index(min(d))
        if i >= 2:  # first way was oriented backwards
            line = line[::-1]
        line += (w if i % 2 == 0 else w[::-1])[1:]
    return line


def main():
    elements = fetch()
    names = {e["id"]: e.get("tags", {}).get("name") for e in elements if e["type"] == "node"}
    features = []
    for rel in (e for e in elements if e["type"] == "relation"):
        line = RELATIONS[rel["id"]]
        kind = "metrorail" if "Metrorail" in line else "metromover"
        ways = [[[round(p["lon"], 6), round(p["lat"], 6)] for p in m["geometry"]]
                for m in rel["members"] if m["type"] == "way" and m["role"] == "" and m.get("geometry")]
        features.append({"type": "Feature", "properties": {"line": line, "kind": kind},
                         "geometry": {"type": "LineString", "coordinates": chain(ways)}})
        stops = [m for m in rel["members"] if m["type"] == "node" and m["role"].startswith("stop")]
        for order, m in enumerate(stops):
            name = (names.get(m["ref"]) or "Station").replace("Metromover ", "").replace("Metrorail ", "")
            features.append({"type": "Feature", "properties": {"name": name, "line": line, "kind": kind, "order": order},
                             "geometry": {"type": "Point", "coordinates": [round(m["lon"], 6), round(m["lat"], 6)]}})
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    print(f"wrote {len(features)} features to {OUT}")


if __name__ == "__main__":
    main()
