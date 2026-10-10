# h4h-miami-2026

Our project for [Hack for Humanity: Miami](https://github.com/AI-Collective-Hackathons/hack-for-humanity-miami) — October 10, 2026, The LAB Miami.

## Submission info

- **Build for Miami track:** 01 Four Forces, One City
- **MLH challenges entered:** Best Open-Source AI Project · Best Use of Gemma 4
- **Model(s) used:** Gemma 4 `gemma-4-26b-a4b-it` via the Gemini API (route summaries in English, Spanish, Haitian Creole); local fallback `gemma4:e4b-it-qat` via Ollama

## What it does

**SombraRoute finds the coolest walk by day and the brightest walk by night**, anywhere between Downtown Miami and Wynwood.

- **Day:** every candidate route is scored by metres walked in direct sun. Shade comes from building shadows computed from the sun's real position (Overture building heights + SunCalc) and the Miami-Dade 2021 tree canopy map.
- **Night:** routes are scored by their longest dark, empty stretch, using Miami-Dade and OpenStreetMap street lights plus places likely open late.
- **Time slider:** drag from 4 PM to 9 PM and the recommended route changes (NW 2nd Ave by day, NW 3rd Ave at night for 300 SW 2nd Ave → The LAB Miami).
- **Gemma 4** (`gemma-4-26b-a4b-it` via the Gemini API) explains the pick in English, Spanish or Haitian Creole, and answers follow-up questions in the **Ask Gemma** chat ("When should I leave?", "Any bus stops on the way?"). It falls back to Gemma 4 running locally in Ollama when offline.
- **Phone app:** open it on a phone and use *Add to Home Screen*; it launches full-screen like a native app (PWA).
- **Evals:** `evals/` checks the shadow physics, route rankings and Gemma's answers (right route, right language, no stigmatizing language about neighborhoods).

Why it matters: heat is Miami's deadliest weather hazard, and the people who walk the most (transit riders, outdoor workers, students) get the least shade. At night, the same people need lit, active streets.

## Tech stack

Python · Flask · SQLite (Supabase/PostGIS ready) · Shapely · SunCalc · Leaflet + OpenStreetMap tiles · Gemma 4 via the Gemini API

## Data sources

- [Overture Maps buildings](https://docs.overturemaps.org/guides/buildings/) (release 2026-09-23.1) — footprints and heights; includes © OpenStreetMap contributors, ODbL
- [Miami-Dade 2021 Urban Tree Canopy land cover](https://gisweb.miamidade.gov/arcgis/rest/services/UrbanTreeCanopy/LandCover_2021/ImageServer) — 2 m land-cover classes
- [Overture Maps places](https://docs.overturemaps.org/guides/places/) (release 2026-09-23.1) — businesses, used for street activity
- [Miami-Dade Street Light Inventory](https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/StreetLightInventory_gdb/FeatureServer) — county-maintained lights
- [Miami-Dade bus stops](https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/Bus_Stop_Maintenance_View_Layer/FeatureServer)
- OpenStreetMap street lamps and `lit=yes` streets via Overpass — night lighting
- OpenStreetMap elevated motorway/trunk bridges (I-95, I-395, SR 836) via Overpass — metres walked under highways
- [City of Miami Police "Crimes (Public)"](https://services1.arcgis.com/CvuPhqcTQpZPT9qY/arcgis/rest/services/Crimes_public_67c0535145c14baf897e47a8d4986539/FeatureServer/0) via the City of Miami Open Data GIS Hub — reported incidents against people near each route, last 12 months (block-level; shown only as a per-route rate, never as a neighborhood map)
- Overture places (police/fire stations, hospitals, hotels, pharmacies, 24h stores) — "safe stops" along the route
- Miami-Dade Traffic Cameras + OpenStreetMap `man_made=surveillance` — collected in `data/cameras.geojson` but not scored (54 points, mostly highway CCTV and plate readers: too sparse for street-level coverage)
- [Photon](https://photon.komoot.io) (OpenStreetMap) — address type-ahead suggestions
- [OpenStreetMap](https://www.openstreetmap.org/copyright) — street network and basemap; walking routes via [FOSSGIS OSRM](https://routing.openstreetmap.de/)

## Running locally

```bash
cp .env.example .env   # add your GEMINI_API_KEY
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.server   # http://localhost:5050 (and http://<your-laptop-ip>:5050 from a phone on the same Wi-Fi)
```

`data/` (including the SQLite store `data/sombra.db`) is committed, so no downloads are needed. To refresh it:

```bash
python scripts/fetch_overture.py && python scripts/fetch_county.py && python scripts/fetch_osm.py
python scripts/build_sqlite.py
```

Evals (scoring regression tests + live Gemma summary checks): see [evals/README.md](evals/README.md).

To use Supabase instead of SQLite, set `SUPABASE_DB_URL` in `.env` and run `python scripts/load_supabase.py`.

## Team

- [@Stuti-Agarwal](https://github.com/Stuti-Agarwal)

## License

[MIT](LICENSE)
