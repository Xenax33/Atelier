"""Research tools (SEAM #3: pure typed functions).

Sources chosen for reliability (per the 2026 SearXNG engine survey): direct APIs first
(Wikimedia feed, Wikipedia search, Semantic Scholar), SearXNG as the general-web layer
when the local instance is up. ALL fetched content is untrusted data, never instructions
(Risk R13), and Wikipedia prose is CC-BY-SA: leads only, facts get rewritten downstream.
"""

from __future__ import annotations

import datetime as _dt

import httpx

from ..config import get_settings

# Wikimedia's robot policy 403s generic UAs: they require an identifying UA with contact.
_UA = {"User-Agent": "AtelierResearch/0.1 (https://github.com/Xenax33/Atelier; saadkbr2@gmail.com) httpx"}
_TIMEOUT = 20.0


def on_this_day(month: int | None = None, day: int | None = None, limit: int = 25) -> list[dict]:
    """Historical events for a date from the Wikimedia feed. Great ideation seed."""
    now = _dt.date.today()
    m, d = month or now.month, day or now.day
    url = f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/{m:02d}/{d:02d}"
    try:
        r = httpx.get(url, headers=_UA, timeout=_TIMEOUT, follow_redirects=True)
        r.raise_for_status()
    except httpx.HTTPError:
        return []
    out = []
    for ev in r.json().get("events", [])[:limit]:
        out.append({"year": ev.get("year"), "text": ev.get("text", "")})
    return out


def wikipedia_search(query: str, limit: int = 5) -> list[dict]:
    """Title + snippet leads (CC-BY-SA: use as leads, never quote prose)."""
    try:
        r = httpx.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": query,
                    "srlimit": limit, "format": "json"},
            headers=_UA, timeout=_TIMEOUT,
        )
        r.raise_for_status()
    except httpx.HTTPError:
        return []
    return [
        {"title": hit["title"], "snippet": hit.get("snippet", "")}
        for hit in r.json().get("query", {}).get("search", [])
    ]


def semantic_scholar_search(query: str, limit: int = 5) -> list[dict]:
    """Paper titles/abstracts via the free Semantic Scholar API."""
    try:
        r = httpx.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": query, "limit": limit, "fields": "title,year,abstract,externalIds"},
            headers=_UA, timeout=_TIMEOUT,
        )
        r.raise_for_status()
    except httpx.HTTPError:
        return []
    return [
        {"title": p.get("title"), "year": p.get("year"),
         "abstract": (p.get("abstract") or "")[:400], "doi": (p.get("externalIds") or {}).get("DOI")}
        for p in r.json().get("data", [])
    ]


def resolve_url(url: str) -> bool:
    """Mechanical citation check: does the URL actually resolve (2xx/3xx)? Never trust
    self-citation (Risk R4) - a claim's source must exist before we call it cited."""
    if not url:
        return False
    try:
        r = httpx.head(url, headers=_UA, timeout=10.0, follow_redirects=True)
        if r.status_code == 405:  # some servers refuse HEAD
            r = httpx.get(url, headers=_UA, timeout=10.0, follow_redirects=True)
        return 200 <= r.status_code < 400
    except httpx.HTTPError:
        return False


def crossref_doi_title(doi: str) -> str:
    """Title registered for a DOI at Crossref, or '' if it does not resolve."""
    if not doi:
        return ""
    try:
        r = httpx.get(f"https://api.crossref.org/works/{doi}", headers=_UA, timeout=15.0)
        r.raise_for_status()
        titles = r.json().get("message", {}).get("title", [])
        return titles[0] if titles else ""
    except (httpx.HTTPError, ValueError):
        return ""


def wikipedia_extract(title: str, sentences: int = 8) -> str:
    """Intro extract of an article. CC-BY-SA: facts get extracted and REWRITTEN downstream."""
    try:
        r = httpx.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "prop": "extracts", "titles": title, "explaintext": 1,
                    "exintro": 1, "exsentences": sentences, "redirects": 1, "format": "json"},
            headers=_UA, timeout=_TIMEOUT,
        )
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
        return next(iter(pages.values()), {}).get("extract", "")
    except (httpx.HTTPError, ValueError):
        return ""


def searxng_search(query: str, limit: int = 8, engines: str = "") -> list[dict]:
    """General web via the local SearXNG instance. Returns [] gracefully when it is not up.

    settings.yml must include json in search.formats or this 403s (documented trap).
    """
    base = get_settings().searxng_base_url.rstrip("/")
    params: dict = {"q": query, "format": "json"}
    if engines:
        params["engines"] = engines
    try:
        r = httpx.get(base + "/search", params=params, headers=_UA, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError):
        return []
    return [
        {"title": x.get("title", ""), "url": x.get("url", ""), "content": x.get("content", "")[:400]}
        for x in data.get("results", [])[:limit]
    ]
