"""Build data/sombra.db (SQLite) from data/*.geojson and data/routes.json. Geometries are stored as GeoJSON text."""
import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app.scoring import COLUMNS, DATA, DB  # noqa: E402


def main():
    DB.unlink(missing_ok=True)
    with sqlite3.connect(DB) as conn:
        for table, cols in COLUMNS.items():
            conn.execute(f"create table {table} (id integer primary key, geom text not null{''.join(f', {c}' for c in cols)})")
            features = [f for f in json.loads((DATA / f"{table}.geojson").read_text())["features"] if f["geometry"]]
            conn.executemany(
                f"insert into {table} (geom{''.join(', ' + c for c in cols)}) values (?{', ?' * len(cols)})",
                [(json.dumps(f["geometry"]), *[f["properties"].get(c) for c in cols]) for f in features],
            )
            print(table, len(features))
        conn.execute("create table routes (name text primary key, distance_m integer not null, geom text not null)")
        conn.executemany("insert into routes values (?, ?, ?)",
                         [(n, r["distance_m"], json.dumps(r["geometry"]))
                          for n, r in json.loads((DATA / "routes.json").read_text()).items()])
    print(DB.name, f"{DB.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
