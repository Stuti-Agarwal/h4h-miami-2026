# h4h-miami-2026

Our project for [Hack for Humanity: Miami](https://github.com/AI-Collective-Hackathons/hack-for-humanity-miami) — October 10, 2026, The LAB Miami.

## Submission info

- **Build for Miami track:** 01 Four Forces, One City
- **MLH challenges entered:** Best Open-Source AI Project · Best Use of Gemma 4
- **Model(s) used:** Gemma 4 `gemma-4-26b-a4b-it` via the Gemini API (route summaries in English, Spanish, Haitian Creole); local fallback `gemma4:e4b-it-qat` via Ollama

## What it does

**SombraRoute finds the coolest walk by day and the busiest, best-lit walk by night**, anywhere between Downtown Miami and Wynwood.

- **Day:** every candidate route is scored by metres walked in direct sun. Shade comes from building shadows computed from the sun's real position (Overture building heights + SunCalc) and the Miami-Dade 2021 tree canopy map.
- **Night / Busiest:** after dark (or when you tap **Busiest**) routes are ranked by street life: storefronts per mile (Overture places) and cars per day on the adjacent roads (FDOT traffic counts). Every ranking also penalizes reported incidents against people and metres walked under elevated highways. Street lights and places open late are shown per route.
- **Time slider:** 6 AM to 11 PM; the recommended route changes with the sun (for 300 SW 2nd Ave → The LAB Miami: NW 2nd Ave at 4 PM, Biscayne Blvd at 9 PM). The map turns dark after sunset.
- **Walk or Transit:** the Transit chip shows nearby bus, Metromover and Metrorail stops at each end and adds a "Metromover + walk" option (only its walking legs are scored). It is listed as an alternative, never the top pick.
- **Start walk:** follows you by GPS with miles and minutes left and the next safe stop (police, fire, hospital, hotel, pharmacy, 24h store). Without GPS, or far from the route, it plays a 30-second preview.
- **SOS:** one tap to call 911 or share your location. **Maps** opens Google Maps directions; **Share** sends your trip.
- **Gemma 4** (`gemma-4-26b-a4b-it` via the Gemini API) explains the pick in English, Spanish or Haitian Creole, and answers follow-up questions in the **Ask Gemma** chat ("Best time to leave?", "Bus stops nearby", "Places to stop"). It falls back to Gemma 4 running locally in Ollama when offline.
- **Onboarding:** four intro cards on the first visit (English, Spanish, Haitian Creole); the **?** button reopens them.
- **Phone app:** open it on a phone and use *Add to Home Screen*; it launches full-screen like a native app (PWA manifest + icons).
- **Evals:** `evals/` checks the shadow physics, route rankings, safety and busy-street metrics, transit routing, place search and Gemma's answers (right route, right language, no stigmatizing language about neighborhoods).

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
- [FDOT Annual Average Daily Traffic](https://services1.arcgis.com/O1JpcwDW8sjYuddV/arcgis/rest/services/Annual_Average_Daily_Traffic_TDA/FeatureServer/0) — cars per day per road segment (I-95, I-395/SR 836 and MacArthur Causeway excluded)
- OpenStreetMap Metromover loops and Metrorail Green Line via Overpass — transit option
- [Photon](https://photon.komoot.io) (OpenStreetMap) — address type-ahead suggestions
- [OpenStreetMap](https://www.openstreetmap.org/copyright) — street network and basemap; walking routes via [FOSSGIS OSRM](https://routing.openstreetmap.de/); geocoding via Nominatim

## Running locally

```bash
cp .env.example .env   # add your GEMINI_API_KEY
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.server   # http://localhost:5050 (and http://<your-laptop-ip>:5050 from a phone on the same Wi-Fi)
```

`data/` (including the SQLite store `data/sombra.db`) is committed, so no downloads are needed. To refresh it:

```bash
python scripts/fetch_overture.py && python scripts/fetch_county.py && python scripts/fetch_osm.py
python scripts/fetch_highways.py && python scripts/fetch_safety.py && python scripts/fetch_traffic.py && python scripts/fetch_transit.py
python scripts/build_sqlite.py
```

Evals: `pip install pytest && python -m pytest -q evals/` (offline tests), plus `python evals/gemma_eval.py` for live Gemma checks. See [evals/README.md](evals/README.md).

### API

| Endpoint | Params |
|---|---|
| `GET /api/routes` | `hour` (0–23.75, default 16), `date` (ISO), `from`/`to` (`lon,lat`; omit for the demo trip), `goal=auto\|busy`, `mode=walk\|transit` |
| `GET /api/summary` | same as `/api/routes` + `lang=English\|Spanish\|Haitian Creole` |
| `POST /api/chat` | JSON: `question`, `history`, `lang` + route params |
| `GET /api/geocode`, `/api/suggest`, `/api/shadows`, `/api/transit` | address lookup, type-ahead, shadow polygons, nearest stops |

To use Supabase instead of SQLite, set `SUPABASE_DB_URL` in `.env` and run `python scripts/load_supabase.py`.

## Team

- [@Stuti-Agarwal](https://github.com/Stuti-Agarwal)

## License

[MIT](LICENSE)
