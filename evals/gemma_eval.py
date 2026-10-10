"""Live eval of app/gemma.summarize: programmatic checks over a small case table.

Run from repo root: python evals/gemma_eval.py   (needs GEMINI_API_KEY in .env)
"""
import json
import pathlib
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from app.gemma import summarize  # noqa: E402
from app.scoring import Scorer, load_routes  # noqa: E402

MIAMI = ZoneInfo("America/New_York")
STREET = {"NW 2nd Ave": "2nd Ave", "NW 3rd Ave": "3rd Ave", "Biscayne Blvd": "Biscayne", "N Miami Ave": "Miami Ave"}
LANG_WORDS = {
    "English": {"the", "route", "street", "shade", "and", "is", "with", "recommend"},
    "Spanish": {"ruta", "calle", "sombra", "la", "el", "es", "con", "recomiendo", "por", "más"},
    "Haitian Creole": {"wout", "lari", "mache", "lonbraj", "ak", "pi", "nou", "se", "gen", "pou"},
}
STIGMA = re.compile(r"\b(unsafe|dangerous|sketchy|crime|criminal|inseguro|insegura|peligros[oa]|danjere|danje)\b", re.I)
HOODS = re.compile(r"\b(overtown|little haiti|ti ayiti|pequeño haití)\b", re.I)
CASES = [(h, lang, False) for h in (9, 16, 21) for lang in ("English", "Spanish", "Haitian Creole")]
CASES.append((16, "English", True))  # routes reversed: recommendation must not follow list order


def rank(scorer, routes, when):
    """Copy of _rank in app/server.py (minus geometry)."""
    scored = [{"name": n, **scorer.score(r["geometry"]["coordinates"], when)} for n, r in routes.items()]
    for s in scored:
        s.pop("samples")
    day = scored[0]["daylight"]
    scored.sort(key=(lambda r: r["sun_exposed_m"]) if day else (lambda r: r["longest_dark_m"]))
    return {"when": when.strftime("%A %b %d, %I:%M %p"), "daylight": day, "recommended": scored[0]["name"], "routes": scored}


def sentences(text):
    t = re.sub(r"\b(Ave|Blvd|St|Dr|N|NW|SW|Mr|Mrs|vs|approx|aprox)\.", r"\1", text)
    return [s for s in re.split(r"(?<=[.!?])\s+", t.strip()) if s.strip()]


def grade(text, best, lang):
    low = text.lower()
    hits = {street: low.find(street.lower()) for street in STREET.values()}
    found = {k: v for k, v in hits.items() if v >= 0}
    words = re.findall(r"[\wèòàé]+", low)
    counts = {l: sum(w in ws for w in words) for l, ws in LANG_WORDS.items()}
    return {
        "mentions_best": STREET[best] in found,
        # first route named should be the recommended one
        "best_first": bool(found) and min(found, key=found.get) == STREET[best],
        "language": max(counts, key=counts.get) == lang,
        "no_stigma": not STIGMA.search(text) and not HOODS.search(text),
        "max_4_sentences": len(sentences(text)) <= 4,
    }


def main():
    scorer, routes = Scorer(), load_routes()
    cache, results = {}, []
    for hour, lang, reverse in CASES:
        if hour not in cache:
            cache[hour] = rank(scorer, routes, datetime(2026, 10, 10, hour, 0, tzinfo=MIAMI))
        scored = dict(cache[hour], routes=list(cache[hour]["routes"]))
        if reverse:
            scored["routes"].reverse()
        out = summarize(scored, lang)
        checks = grade(out["text"], scored["recommended"], lang)
        results.append({"hour": hour, "language": lang, "reversed": reverse, "recommended": scored["recommended"],
                        "engine": out["engine"], "gemini_api": out["engine"].startswith("gemini-api"),
                        "checks": checks, "passed": all(checks.values()), "text": out["text"]})

    names = list(results[0]["checks"])
    print(f"{'case':<28}" + "".join(f"{n:<16}" for n in names) + f"{'engine':<12}result")
    for r in results:
        case = f"{r['hour']}h {r['language']}{' (rev)' if r['reversed'] else ''}"
        cells = "".join(f"{'ok' if r['checks'][n] else 'FAIL':<16}" for n in names)
        print(f"{case:<28}{cells}{'gemini' if r['gemini_api'] else r['engine'][:11]:<12}{'PASS' if r['passed'] else 'FAIL'}")
    score = sum(r["passed"] for r in results) / len(results)
    print(f"\noverall: {sum(r['passed'] for r in results)}/{len(results)} = {score:.0%}"
          f"  (gemini-api engine on {sum(r['gemini_api'] for r in results)}/{len(results)})")
    for r in results:
        if not r["passed"]:
            print(f"\n--- FAIL {r['hour']}h {r['language']} (best {r['recommended']}): {r['text']}")

    out_dir = ROOT / "evals" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"gemma_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps({"score": score, "results": results}, indent=2, ensure_ascii=False))
    print(f"\nwrote {path.relative_to(ROOT)}")
    sys.exit(0 if score >= 0.8 else 1)


if __name__ == "__main__":
    main()
