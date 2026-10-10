# h4h-miami-2026

Our project for [Hack for Humanity: Miami](https://github.com/AI-Collective-Hackathons/hack-for-humanity-miami) — October 10, 2026, The LAB Miami.

## Submission info

- **Build for Miami track:** 01 Four Forces, One City
- **MLH challenges entered:** Best Open-Source AI Project · Best Use of Gemma 4
- **Model(s) used:** Gemma 4 `gemma-4-26b-a4b-it` via the Gemini API (route summaries in English, Spanish, Haitian Creole); local fallback `gemma4:e4b-it-qat` via Ollama

## What it does

Finds the shadiest walking route across Miami for a given time of day. Each candidate route is scored by tree canopy plus building shadows computed from the sun's position, and Gemma 4 explains the recommendation.

## Tech stack

Python · Flask · SQLite (Supabase/PostGIS ready) · Shapely · SunCalc · Leaflet + OpenStreetMap tiles · Gemma 4 via the Gemini API

## Data sources

- [Overture Maps buildings](https://docs.overturemaps.org/guides/buildings/) (release 2026-09-23.1) — footprints and heights; includes © OpenStreetMap contributors, ODbL
- [Miami-Dade 2021 Urban Tree Canopy land cover](https://gisweb.miamidade.gov/arcgis/rest/services/UrbanTreeCanopy/LandCover_2021/ImageServer) — 2 m land-cover classes
- [Overture Maps places](https://docs.overturemaps.org/guides/places/) (release 2026-09-23.1) — businesses, used for street activity
- [Miami-Dade Street Light Inventory](https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/StreetLightInventory_gdb/FeatureServer) — county-maintained lights
- [Miami-Dade bus stops](https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/Bus_Stop_Maintenance_View_Layer/FeatureServer)
- OpenStreetMap street lamps and `lit=yes` streets via Overpass — night lighting
- [OpenStreetMap](https://www.openstreetmap.org/copyright) — street network and basemap; walking routes via [FOSSGIS OSRM](https://routing.openstreetmap.de/)

## Running locally

```bash
cp .env.example .env   # add your GEMINI_API_KEY
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.server   # http://localhost:5050
```

`data/` (including the SQLite store `data/sombra.db`) is committed, so no downloads are needed. To refresh it:

```bash
python scripts/fetch_overture.py && python scripts/fetch_county.py && python scripts/fetch_osm.py
python scripts/build_sqlite.py
```

To use Supabase instead of SQLite, set `SUPABASE_DB_URL` in `.env` and run `python scripts/load_supabase.py`.

## Team

- [@Stuti-Agarwal](https://github.com/Stuti-Agarwal)

## License

[MIT](LICENSE)
