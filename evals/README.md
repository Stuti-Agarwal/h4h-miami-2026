# Evals

**Scoring (deterministic, no network, ~10 s):** shadow direction/length on a synthetic building, night behavior, route-ranking regression on the 4 cached routes, metric bounds, land-cover classes.

```bash
.venv/bin/pip install pytest   # not in requirements.txt
.venv/bin/python -m pytest evals/test_scoring.py -q
```

**Other offline tests (no network):**

- `test_highways.py`: elevated-highway data loads, a route along a highway counts metres under it and a far route doesn't, and the demo ranking still has a winner.
- `test_safety.py`: reported incidents load, a route through a dense cluster picks them up, safe stops are well-formed and capped, and ranking with incidents still has a winner.
- `test_busy.py`: `goal=busy` loads FDOT traffic, returns storefronts/km and cars per day per route, night hours default to busy, and an invalid goal falls back to auto.
- `test_suggest.py`: place search on the local SQLite db: "lab" variants rank The LAB Miami first, multi-word queries match all words, Bayfront Park is found, and results come back with tiers and distinct names.
- `test_transit.py`: `/api/transit` returns up to 3 nearest bus/Metromover/Metrorail stops per end, sorted and within 1 km, and returns 400 outside the bbox. `mode=transit` adds a "Metromover + walk" option that is listed last and never the pick, an invalid mode falls back to walk, and walk mode matches the default.

Run every offline test at once:

```bash
.venv/bin/python -m pytest -q evals/
```

**Gemma summaries (live, ~1 min, needs `GEMINI_API_KEY` in `.env`):** 10 cases (9h/16h/21h x English/Spanish/Haitian Creole + one with routes reversed), graded on: names the recommended route, names it first, right language, no stigmatizing words or neighborhood names, at most 4 sentences. Prints a table, writes `evals/results/gemma_<timestamp>.json`, exits 1 if under 80% pass.

```bash
.venv/bin/python evals/gemma_eval.py
```

`evals/results/` holds generated output and is gitignored.
