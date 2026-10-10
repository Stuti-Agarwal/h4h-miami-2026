"""Gemma 4 route summary: Gemini API first, local Ollama fallback."""
import os

import requests

PROMPT = """You are a walking guide in Miami. Recommend one route for a pedestrian in {language}, in at most 3 short sentences (under 60 words).
It is {when} ({mode}). Routes were ranked by {rule}.
The recommended route is {best}. Recommend {best} and say why, comparing it with the others.
Describe streets only by shade, lighting, open businesses, storefronts and car traffic. Fewer metres under elevated highways is better. Never call a neighborhood or its people unsafe. Call police data only "reported incidents"; never name or characterize a neighborhood, and never call a street or area dangerous or unsafe. Stick to the numbers given and do not exaggerate.
Routes:
{routes}{weather}"""


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
Recommended: {best}. On {best}, by departure time: {other_times}.{weather}
Answer only from these numbers and general walking-safety common sense; if the data can't answer, say so.
Describe streets only by shade, lighting, open businesses, storefronts and car traffic. Fewer metres under elevated highways is better. Never call a neighborhood or its people unsafe. Call police data only "reported incidents"; never name or characterize a neighborhood, and never call a street or area dangerous or unsafe.
Conversation so far:
{history}
Question: {question}"""


KM_PER_MI = 1.609344


def _vs(value, base, unit, more, less, digits=0):
    d = value - base
    return ("same as recommended" if round(abs(d), digits) == 0
            else f"{abs(d):.{digits}f} {unit} {more if d > 0 else less} than recommended")


def _miles(r):
    """Route metrics with distance in miles and per-km rates per mile, for the prompt text."""
    return {**r, "distance_mi": round(r["distance_m"] / 1000 / KM_PER_MI, 1),
            "storefronts_per_mi": round(r["storefronts_per_km"] * KM_PER_MI, 1),
            "incidents_per_mi": round(r["incidents_per_km"] * KM_PER_MI, 1),
            "sun_mi": round(r["sun_exposed_m"] / 1000 / KM_PER_MI, 1),
            "dark_ft": round(r["longest_dark_m"] * 3.28084), "highway_ft": round(r["under_highway_m"] * 3.28084)}


def _route_lines(scored):
    # Precomputed comparisons: small local models get "longer/shorter" wrong when left to do the arithmetic.
    best = next(r for r in scored["routes"] if r["name"] == scored["recommended"])

    b = _miles(best)

    def line(r):
        is_best, r = r is best, _miles(r)
        cmp = (lambda v, unit, more, less, digits=0: "") if is_best else (
            lambda v, unit, more, less, digits=0: f" ({_vs(r[v], b[v], unit, more, less, digits)})")
        light = (f"{r['sun_exposed_m'] / 1609.344:.1f} mi in direct sun{cmp('sun_mi', 'mi', 'more', 'less', 1)}, {r['shade']:.0%} shaded"
                 if scored["daylight"] else
                 f"longest dark, empty stretch {r['longest_dark_m'] * 3.28084:.0f} ft{cmp('dark_ft', 'ft', 'more', 'less')}, {r['lit']:.0%} lit")
        return (f"- {r['name']}{' (RECOMMENDED)' if is_best else ''}: {r['distance_mi']} mi"
                f"{cmp('distance_mi', 'mi', 'longer', 'shorter', 1)}, {light}, "
                f"{r['under_highway_m'] * 3.28084:.0f} ft under elevated highways{cmp('highway_ft', 'ft', 'more', 'less')}, "
                f"{r['active']:.0%} near open venues, {r['storefronts_per_mi']} storefronts/mile"
                f"{cmp('storefronts_per_mi', 'per mile', 'more', 'fewer')}, "
                f"~{r['traffic_aadt']} cars/day on adjacent roads{cmp('traffic_aadt', 'cars/day', 'more', 'fewer')}, "
                f"{r['transit']:.0%} near bus stops, "
                f"{r['incidents_per_mi']} reported incidents against people per mile"
                f"{cmp('incidents_per_mi', 'per mile', 'more', 'fewer')}, "
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


def _weather(scored):
    """Prompt lines for NWS alerts and a rainy/stormy departure forecast; empty when calm or unknown."""
    w = scored.get("weather") or {}
    lines = []
    if w.get("alerts"):
        lines.append("Weather alerts: " + "; ".join(f"{a.get('event')} until {a.get('ends')}" for a in w["alerts"]))
    now = w.get("now")
    if now and (now.get("rain_pct", 0) >= 30 or now.get("thunder")):
        lines.append(f"Forecast at departure: {now.get('short')}, {now.get('rain_pct', 0)}% chance of rain")
    if not lines:
        return ""
    lines.append("If there is a storm/thunder alert or thunder forecast, advise waiting or taking covered transit; "
                 "otherwise mention rain chance briefly. Don't exaggerate.")
    return "\n" + "\n".join(lines)


def summarize(scored, language="English"):
    """scored: the /api/routes payload. Returns {"text", "engine"}."""
    day = scored["daylight"]
    prompt = PROMPT.format(
        language=language, when=scored["when"], routes=_route_lines(scored), best=scored["recommended"],
        mode="daytime" if day else "night", rule=_rule(scored), weather=_weather(scored),
    )
    return _generate(prompt, "Route summary unavailable right now.")


def chat(scored, question, history, language="English", other_times="unknown"):
    """Answer a free-text question about the scored routes. history: [{"role": "user"|"gemma", "text"}]."""
    past = "\n".join(f"{m.get('role', 'user')}: {str(m.get('text', ''))[:300]}" for m in history) or "(none)"
    prompt = CHAT_PROMPT.format(
        language=language, when=scored["when"], mode="daytime" if scored["daylight"] else "night",
        routes=_route_lines(scored), best=scored["recommended"], rule=_rule(scored), history=past, question=question, other_times=other_times,
        weather=_weather(scored),
    )
    return _generate(prompt, "Sorry, I can't answer right now. Try again in a moment.")
