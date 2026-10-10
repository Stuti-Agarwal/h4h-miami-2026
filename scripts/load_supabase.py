"""Load data/*.geojson and data/routes.json into Supabase Postgres (replaces existing rows)."""
import json
import os
import pathlib

import psycopg
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
COLUMNS = {
    "buildings": ["height", "num_floors"],
    "places": ["name", "category", "confidence"],
    "lights": [],
    "stops": [],
}


def main():
    load_dotenv(ROOT / ".env")
    with psycopg.connect(os.environ["SUPABASE_DB_URL"]) as conn, conn.cursor() as cur:
        cur.execute((ROOT / "supabase" / "schema.sql").read_text())
        for table, cols in COLUMNS.items():
            features = [f for f in json.loads((DATA / f"{table}.geojson").read_text())["features"] if f["geometry"]]
            cur.execute(f"truncate {table}")
            names = ", ".join(["geom", *cols])
            values = ", ".join(["ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)", *["%s"] * len(cols)])
            cur.executemany(
                f"insert into {table} ({names}) values ({values})",
                [(json.dumps(f["geometry"]), *[f["properties"].get(c) for c in cols]) for f in features],
            )
            print(table, len(features))
        cur.execute("truncate routes")
        for name, r in json.loads((DATA / "routes.json").read_text()).items():
            cur.execute("insert into routes (name, distance_m, geom) values (%s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))",
                        (name, r["distance_m"], json.dumps(r["geometry"])))
        print("routes ok")


if __name__ == "__main__":
    main()
