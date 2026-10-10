"""Extract Overture buildings and places for the demo area into data/*.geojson (one-time, ~5 min)."""
import json
import pathlib

import duckdb

RELEASE = "2026-09-23.1"
BBOX = (-80.212, 25.765, -80.184, 25.807)  # xmin, ymin, xmax, ymax: Downtown/Brickell -> Wynwood
DATA = pathlib.Path(__file__).resolve().parent.parent / "data"

QUERIES = {
    "buildings": "SELECT ST_AsGeoJSON(geometry) g, height, num_floors FROM {src}",
    "places": "SELECT ST_AsGeoJSON(geometry) g, names.primary AS name, basic_category AS category, confidence FROM {src}",
}
THEME = {"buildings": "buildings/type=building", "places": "places/type=place"}


def main():
    con = duckdb.connect()
    con.sql("INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    xmin, ymin, xmax, ymax = BBOX
    for name, sql in QUERIES.items():
        src = (f"read_parquet('s3://overturemaps-us-west-2/release/{RELEASE}/theme={THEME[name]}/*', hive_partitioning=1) "
               f"WHERE bbox.xmax > {xmin} AND bbox.xmin < {xmax} AND bbox.ymax > {ymin} AND bbox.ymin < {ymax}")
        rows = con.sql(sql.format(src=src)).fetchall()
        cols = [c for c in con.sql(sql.format(src=src) + " LIMIT 0").columns][1:]
        features = [{"type": "Feature", "geometry": json.loads(r[0]), "properties": dict(zip(cols, r[1:]))} for r in rows]
        (DATA / f"{name}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}))
        print(name, len(features))


if __name__ == "__main__":
    main()
