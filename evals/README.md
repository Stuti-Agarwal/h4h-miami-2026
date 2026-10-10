# Evals

**Scoring (deterministic, no network, ~10 s):** shadow direction/length on a synthetic building, night behavior, route-ranking regression on the 4 cached routes, metric bounds, land-cover classes.

```bash
.venv/bin/pip install pytest   # not in requirements.txt
.venv/bin/python -m pytest evals/test_scoring.py -q
```

**Gemma summaries (live, ~1 min, needs `GEMINI_API_KEY` in `.env`):** 10 cases (9h/16h/21h x English/Spanish/Haitian Creole + one with routes reversed), graded on: names the recommended route, names it first, right language, no stigmatizing words or neighborhood names, at most 4 sentences. Prints a table, writes `evals/results/gemma_<timestamp>.json`, exits 1 if under 80% pass.

```bash
.venv/bin/python evals/gemma_eval.py
```
