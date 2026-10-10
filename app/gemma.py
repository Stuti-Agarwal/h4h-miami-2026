"""Gemma 4 route summary: Gemini API first, local Ollama fallback."""
import os

import requests

PROMPT = """You are a walking guide in Miami. Recommend one route for a pedestrian in {language}, in 3 short sentences.
It is {when} ({mode}). Routes were ranked by {rule}.
The recommended route is {best}. Recommend {best} and say why, comparing it with the others.
Describe streets only by shade, lighting and open businesses. Never call a neighborhood or its people unsafe.
Routes (distance, sun-exposed metres, % shaded, longest dark stretch at night, % near open venues):
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


def summarize(scored, language="English"):
    """scored: the /api/routes payload. Returns {"text", "engine"}."""
    day = scored["daylight"]
    lines = "\n".join(
        f"- {r['name']}: {r['distance_m']} m, {r['sun_exposed_m']} m in sun, {r['shade']:.0%} shaded, "
        f"longest dark {r['longest_dark_m']} m, {r['active']:.0%} near open venues"
        for r in scored["routes"]
    )
    prompt = PROMPT.format(
        language=language, when=scored["when"], routes=lines, best=scored["recommended"],
        mode="daytime" if day else "night",
        rule="fewest metres in direct sun" if day else "shortest dark, empty stretch",
    )
    for engine, call in (("gemini-api:" + os.environ.get("GEMMA_MODEL", "gemma-4-26b-a4b-it"), _gemini),
                         ("ollama:" + os.environ.get("OLLAMA_MODEL", "gemma4:e4b-it-qat"), _ollama)):
        try:
            text = call(prompt)
            if text:
                return {"text": text, "engine": engine}
        except (requests.RequestException, KeyError, IndexError):
            continue
    return {"text": "Route summary unavailable right now.", "engine": "none"}
