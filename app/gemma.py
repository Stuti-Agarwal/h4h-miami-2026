"""Gemma 4 route summary: Gemini API first, local Ollama fallback."""
import os

import requests

PROMPT = """You are a walking guide in Miami. Recommend one route for a pedestrian in {language}, in at most 3 short sentences (under 60 words).
It is {when} ({mode}). Routes were ranked by {rule}.
The recommended route is {best}. Recommend {best} and say why, comparing it with the others.
Describe streets only by shade, lighting, open businesses, storefronts and car traffic. Fewer metres under elevated highways is better. Never call a neighborhood or its people unsafe. Call police data only "reported incidents"; never name or characterize a neighborhood, and never call a street or area dangerous or unsafe. Stick to the numbers given and do not exaggerate.
Routes:
{routes}"""


def _gemini(prompt):
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{os.environ.get('GEMMA_MODEL', 'gemma-4-26b-a4b-it')}:generateContent",
        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"thinkingConfig": {"thinkingLevel": "minimal"}}},
        timeout=30,
    )
    r.raise_for_status()
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()


def _ollama(prompt):
    r = requests.post(
        f"{os.environ.get('OLLAMA_URL', 'http://localhost:11434')}/api/chat",
        json={"model": os.environ.get("OLLAMA_MODEL", "gemma4:e4b-it-qat"), "stream": False, "think": False,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["message"]["content"].strip()


CHAT_PROMPT = """You are a walking guide in Miami answering a pedestrian's question in {language}, in at most 3 short sentences (under 60 words).
It is {when} ({mode}). Routes were ranked by {rule}. Their candidate routes:
{routes}
Recommended: {best}. On {best}, by departure time: {other_times}.
Answer only from these numbers and general walking-safety common sense; if the data can't answer, say so.
Describe streets only by shade, lighting, open businesses, storefronts and car traffic. Fewer metres under elevated highways is better. Never call a neighborhood or its people unsafe. Call police data only "reported incidents"; never name or characterize a neighborhood, and never call a street or area dangerous or unsafe.
Conversation so far:
{history}
Question: {question}"""


def _vs(value, base, unit, more, less):
    d = value - base
    return "same as recommended" if abs(d) < 1 else f"{abs(d):.0f} {unit} {more if d > 0 else less} than recommended"


def _route_lines(scored):
    # Precomputed comparisons: small local models get "longer/shorter" wrong when left to do the arithmetic.
    best = next(r for r in scored["routes"] if r["name"] == scored["recommended"])

    def line(r):
        cmp = (lambda v, unit, more, less: "") if r is best else (lambda v, unit, more, less: f" ({_vs(r[v], best[v], unit, more, less)})")
        light = (f"{r['sun_exposed_m']} m in direct sun{cmp('sun_exposed_m', 'm', 'more', 'less')}, {r['shade']:.0%} shaded"
                 if scored["daylight"] else
                 f"longest dark, empty stretch {r['longest_dark_m']} m{cmp('longest_dark_m', 'm', 'more', 'less')}, {r['lit']:.0%} lit")
        return (f"- {r['name']}{' (RECOMMENDED)' if r is best else ''}: {r['distance_m']} m"
                f"{cmp('distance_m', 'm', 'longer', 'shorter')}, {light}, "
                f"{r['under_highway_m']} m under elevated highways{cmp('under_highway_m', 'm', 'more', 'less')}, "
                f"{r['active']:.0%} near open venues, {r['storefronts_per_km']} storefronts/km"
                f"{cmp('storefronts_per_km', 'per km', 'more', 'fewer')}, "
                f"~{r['traffic_aadt']} cars/day on adjacent roads{cmp('traffic_aadt', 'cars/day', 'more', 'fewer')}, "
                f"{r['transit']:.0%} near bus stops, "
                f"{r['incidents_per_km']} reported incidents against people per km"
                f"{cmp('incidents_per_km', 'per km', 'more', 'fewer')}, "
                f"{len(r['safe_stops'])} safe stops (police, fire, hospital, hotels, pharmacies, 24h stores)")

    return "\n".join(line(r) for r in scored["routes"])


def _generate(prompt, fallback):
    for engine, call in (("gemini-api:" + os.environ.get("GEMMA_MODEL", "gemma-4-26b-a4b-it"), _gemini),
                         ("ollama:" + os.environ.get("OLLAMA_MODEL", "gemma4:e4b-it-qat"), _ollama)):
        try:
            text = call(prompt)
            if text:
                return {"text": text, "engine": engine}
        except (requests.RequestException, KeyError, IndexError):
            continue
    return {"text": fallback, "engine": "none"}


def _rule(scored):
    if scored.get("goal") == "busy":
        return "most storefronts and car traffic, plus fewer police reports and less walking under highways"
    return (("fewest metres in direct sun" if scored["daylight"] else "shortest dark, empty stretch")
            + ", plus least walking under elevated highways")


def summarize(scored, language="English"):
    """scored: the /api/routes payload. Returns {"text", "engine"}."""
    day = scored["daylight"]
    prompt = PROMPT.format(
        language=language, when=scored["when"], routes=_route_lines(scored), best=scored["recommended"],
        mode="daytime" if day else "night", rule=_rule(scored),
    )
    return _generate(prompt, "Route summary unavailable right now.")


def chat(scored, question, history, language="English", other_times="unknown"):
    """Answer a free-text question about the scored routes. history: [{"role": "user"|"gemma", "text"}]."""
    past = "\n".join(f"{m.get('role', 'user')}: {str(m.get('text', ''))[:300]}" for m in history) or "(none)"
    prompt = CHAT_PROMPT.format(
        language=language, when=scored["when"], mode="daytime" if scored["daylight"] else "night",
        routes=_route_lines(scored), best=scored["recommended"], rule=_rule(scored), history=past, question=question, other_times=other_times,
    )
    return _generate(prompt, "Sorry, I can't answer right now. Try again in a moment.")
