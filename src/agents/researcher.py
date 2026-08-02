"""Researcher agent (ideation half): gather raw material, propose pitched topic ideas.

The user picks one in Discord (or supplies their own via /new-short). v1's second half
adds per-topic evidence gathering + the fact-checker; this module is deliberately only
about IDEAS.
"""

from __future__ import annotations

import pathlib
import random

from ..gateway.client import chat_json
from ..tools.research import (
    on_this_day,
    searxng_search,
    semantic_scholar_search,
    wikipedia_extract,
    wikipedia_search,
)

IDEAS_SCHEMA = {
    "type": "object",
    "properties": {
        "ideas": {
            "type": "array",
            "minItems": 4,
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "pitch": {"type": "string"},
                    "hook_angle": {"type": "string"},
                },
                "required": ["topic", "pitch", "hook_angle"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["ideas"],
    "additionalProperties": False,
}

_SEED_QUERIES = [
    "surprising experiment history of physics",
    "forgotten scientist discovery story",
    "accidental scientific discovery",
    "history of astronomy strange observation",
    "medical history breakthrough story",
    "history of chemistry dramatic discovery",
    "mathematics history famous problem",
    "invention that changed the world by accident",
]

_SYSTEM = """You are the topic researcher for a science-history Shorts channel.
From the raw material, propose DIVERSE short ideas (different sciences, eras, moods).

Rules per idea:
- topic: one concrete, specific story or fact (a person, an event, an experiment), not a broad theme.
- pitch: 1-2 sentences on what the 60-second story would be. Vivid but strictly factual.
- hook_angle: the curiosity gap the hook would open, in one sentence.
- Prefer stories that are visual (things a flat-vector illustration can show) and mainstream-documented.
- NEVER propose topics matching the already-produced list.
- No morbid-shock content, no clickbait framing.
"""


def _past_topics() -> list[str]:
    """Titles of already-produced runs (cheap dedup until the vector memory lands)."""
    out = []
    for meta in pathlib.Path("state/runs").glob("*/metadata.md"):
        try:
            first = meta.read_text(encoding="utf-8").splitlines()[0]
            out.append(first.lstrip("# ").strip())
        except (OSError, IndexError):
            continue
    return out


_QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "queries": {"type": "array", "minItems": 2, "maxItems": 3, "items": {"type": "string"}},
    },
    "required": ["subject", "queries"],
    "additionalProperties": False,
}


def make_queries(topic: str) -> dict:
    """Distill a narrative topic into search-engine-shaped queries. Raw story phrasings
    retrieve junk (measured: a Marie Curie topic fetched a Douglas Mawson article)."""
    return chat_json(
        messages=[
            {"role": "system", "content":
                "Turn the topic into search inputs. subject: ONLY the primary person/thing/event "
                "name, exactly as an encyclopedia article is titled (topic 'the day Marie Curie's "
                "notebooks became radioactive' -> subject 'Marie Curie'; never a descriptive "
                "phrase). queries: 2-3 short keyword search queries covering the key facts to "
                "verify. No filler words."},
            {"role": "user", "content": topic},
        ],
        schema=_QUERY_SCHEMA, schema_name="queries", temperature=0.2, max_tokens=200,
    )


def gather_evidence(topic: str, max_items: int = 10) -> list[dict]:
    """Evidence pack for a chosen topic: [{source, title, text}]. The scriptwriter grounds
    beats in THIS, and the fact-checker audits against it. Untrusted data, never instructions."""
    try:
        q = make_queries(topic)
        subject, queries = q["subject"], q["queries"]
    except Exception:  # noqa: BLE001 - fall back to the raw topic
        subject, queries = topic, [topic]
    evidence: list[dict] = []
    for hit in wikipedia_search(subject, limit=3):
        text = wikipedia_extract(hit["title"])
        if text:
            url = "https://en.wikipedia.org/wiki/" + hit["title"].replace(" ", "_")
            evidence.append({"source": "wikipedia", "title": hit["title"], "text": text[:1500], "url": url})
    for query in queries:
        for x in searxng_search(query, limit=3):
            if x.get("content"):
                evidence.append({"source": "web", "title": x["title"], "text": x["content"], "url": x.get("url", "")})
    from ..tools.research import paper_search

    papers = paper_search(subject, limit=2) or semantic_scholar_search(subject, limit=3)
    for p in papers:
        if p.get("abstract"):
            url = p.get("url") or (f"https://doi.org/{p['doi']}" if p.get("doi") else "")
            evidence.append({"source": "paper", "title": p["title"] or "", "text": p["abstract"],
                             "url": url, "doi": p.get("doi") or ""})
    return evidence[:max_items]


def evidence_digest(evidence: list[dict]) -> str:
    return "\n\n".join(
        f"[{i}] ({e['source']}) {e['title']}\n{e['text']}" for i, e in enumerate(evidence)
    )


def propose_ideas(n: int = 6, hint: str = "") -> list[dict]:
    events = on_this_day(limit=20)
    seeds = random.sample(_SEED_QUERIES, k=2)
    leads = []
    for q in seeds:
        leads += wikipedia_search(q, limit=4)
        leads += searxng_search(q, limit=4)  # [] until the local instance is up

    material = "ON THIS DAY IN HISTORY:\n" + "\n".join(
        f"- {e['year']}: {e['text']}" for e in events if e.get("text")
    )
    if leads:
        material += "\n\nSEARCH LEADS:\n" + "\n".join(
            f"- {x.get('title', '')}: {x.get('snippet', x.get('content', ''))}" for x in leads
        )
    past = _past_topics()
    if past:
        material += "\n\nALREADY PRODUCED (never repropose):\n" + "\n".join(f"- {t}" for t in past)
    user = f"Propose {n} ideas from this material (you may also draw on well-documented knowledge):\n\n{material}"
    if hint:
        user += f"\n\nUser steer: {hint}"
    result = chat_json(
        messages=[{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
        schema=IDEAS_SCHEMA, schema_name="ideas", temperature=0.9, max_tokens=1800,
    )
    ideas = result["ideas"][:n]
    # Vector dedup against everything already produced (prompt-level dedup is the belt,
    # this is the suspenders - and it scales past what fits in a prompt).
    try:
        from ..store.memory import is_duplicate

        kept = []
        for idea in ideas:
            dup, match = is_duplicate(f"{idea['topic']}. {idea['pitch']}")
            if not dup:
                kept.append(idea)
        ideas = kept or ideas
    except Exception:  # noqa: BLE001 - dedup failure must never block ideation
        pass
    return ideas
