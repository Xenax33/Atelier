"""Research tools (SEAM #3: pure typed functions).

Sources chosen for reliability (per the 2026 SearXNG engine survey): direct APIs first
(Wikimedia feed, Wikipedia search, Semantic Scholar), SearXNG as the general-web layer
when the local instance is up. ALL fetched content is untrusted data, never instructions
(Risk R13), and Wikipedia prose is CC-BY-SA: leads only, facts get rewritten downstream.
"""

from __future__ import annotations

import datetime as _dt
import re as _re

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


# Identifier regexes vendored from open-science pdf_extract.py (MIT; see
# docs/research/2026-08-01-open-science-repo-assessment.md). Note the old-style arXiv id
# form and the trailing-punctuation cleanup - both classic extraction bugs.
DOI_RE = _re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")
ARXIV_RE = _re.compile(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b")
ARXIV_OLD_RE = _re.compile(r"\b[a-z-]+(?:\.[A-Z]{2})?/\d{7}\b")
PMID_RE = _re.compile(r"\bPMID:?\s*(\d{6,8})\b")


def clean_doi(doi: str) -> str:
    """Strip trailing punctuation that sentence context glues onto extracted DOIs."""
    return doi.rstrip(".,;)]}\"'")


def title_similarity(a: str, b: str) -> float:
    """0..1 similarity for citation title matching (stdlib; no fuzz dependency)."""
    import difflib

    return difflib.SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


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


def paper_search(query: str, limit: int = 4) -> list[dict]:
    """Academic papers via paper-search-mcp's clients (MIT): arXiv + EuropePMC. More
    reliable than anonymous Semantic Scholar (which 429s). Same shape as the S2 tool.
    NOTE: the package also ships a sci_hub client - never use it (ADR-0006 spirit)."""
    out: list[dict] = []
    try:
        from paper_search_mcp.academic_platforms.arxiv import ArxivSearcher
        from paper_search_mcp.academic_platforms.europepmc import EuropePMCSearcher

        for searcher in (ArxivSearcher(), EuropePMCSearcher()):
            try:
                for p in searcher.search(query, max_results=limit):
                    out.append({
                        "title": p.title, "year": str(getattr(p, "published_date", ""))[:4],
                        "abstract": (p.abstract or "")[:400], "doi": p.doi or "",
                        "url": (f"https://doi.org/{p.doi}" if p.doi else getattr(p, "url", "")),
                    })
            except Exception:  # noqa: BLE001 - one source failing must not kill the other
                continue
    except ImportError:
        pass
    return out[: limit * 2]


def chronicling_america_search(query: str, limit: int = 3) -> list[dict]:
    """Historical US newspaper pages via the loc.gov JSON API (R&D 4.6): how a discovery
    was reported AT THE TIME. The legacy chroniclingamerica.loc.gov API was retired in
    2025 - pre-2025 tutorials point at a dead endpoint. Pre-1929 pages are public domain.
    loc.gov rate-limits bursts and 403s some networks (it 403'd the work laptop during
    development, 2026-08-06) - fail-soft like every adapter here; VERIFY from the studio
    box once."""
    try:
        r = httpx.get(
            "https://www.loc.gov/collections/chronicling-america/",
            params={"q": query, "fo": "json", "c": limit},
            headers=_UA, timeout=_TIMEOUT, follow_redirects=True,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
    except (httpx.HTTPError, ValueError):
        return []
    out = []
    for x in results[:limit]:
        desc = x.get("description", "")
        if isinstance(desc, list):
            desc = " ".join(str(d) for d in desc)
        out.append({"title": str(x.get("title", "")), "date": str(x.get("date", "")),
                    "text": str(desc)[:400], "url": str(x.get("url", ""))})
    return out


def openlibrary_search(query: str, limit: int = 3) -> list[dict]:
    """Book leads from Open Library (keyless). Mostly title/year/author metadata (the
    first_sentence field is usually absent - verified live 2026-08-06), so these ground
    'documented by <year>' claims rather than carrying quotable text."""
    try:
        r = httpx.get(
            "https://openlibrary.org/search.json",
            params={"q": query, "limit": limit,
                    "fields": "title,first_publish_year,author_name,key"},
            headers=_UA, timeout=_TIMEOUT,
        )
        r.raise_for_status()
        docs = r.json().get("docs", [])
    except (httpx.HTTPError, ValueError):
        return []
    return [
        {"title": str(d.get("title", "")), "year": str(d.get("first_publish_year") or ""),
         "author": (d.get("author_name") or ["unknown"])[0],
         "url": "https://openlibrary.org" + str(d.get("key", ""))}
        for d in docs[:limit]
    ]


def ads_search(query: str, limit: int = 3) -> list[dict]:
    """NASA ADS papers - the only source covering the 1840s-1970s astronomy record
    (R&D 4.6). Needs the free token in .env (ADS_API_TOKEN, quota ~5000/day); returns
    [] while the token is unset so the adapter ships dormant."""
    token = get_settings().ads_api_token
    if not token:
        return []
    try:
        r = httpx.get(
            "https://api.adsabs.harvard.edu/v1/search/query",
            params={"q": query, "fl": "title,year,abstract,doi", "rows": limit},
            headers={**_UA, "Authorization": f"Bearer {token}"}, timeout=_TIMEOUT,
        )
        r.raise_for_status()
        docs = r.json().get("response", {}).get("docs", [])
    except (httpx.HTTPError, ValueError):
        return []
    return [
        {"title": (d.get("title") or [""])[0], "year": str(d.get("year") or ""),
         "abstract": (d.get("abstract") or "")[:400], "doi": (d.get("doi") or [""])[0]}
        for d in docs[:limit]
    ]


def wikidata_year_facts(term: str) -> dict:
    """Entity-link a term on Wikidata (CC0, keyless) and return its dated facts:
    {label, description, years: {birth/death/discovered: int}}. {} when the term does
    not link or carries no dates. Birth/death (P569/P570) are densely populated;
    discovery time (P575) is sparse - verified live 2026-08-06."""
    try:
        r = httpx.get("https://www.wikidata.org/w/api.php",
                      params={"action": "wbsearchentities", "search": term, "language": "en",
                              "format": "json", "limit": 1}, headers=_UA, timeout=_TIMEOUT)
        r.raise_for_status()
        hits = r.json().get("search", [])
        if not hits:
            return {}
        qid = hits[0]["id"]
        r = httpx.get("https://www.wikidata.org/w/api.php",
                      params={"action": "wbgetentities", "ids": qid, "props": "claims",
                              "format": "json"}, headers=_UA, timeout=_TIMEOUT)
        r.raise_for_status()
        claims = r.json().get("entities", {}).get(qid, {}).get("claims", {})
    except (httpx.HTTPError, ValueError, KeyError):
        return {}
    years = {}
    for prop, tag in (("P569", "birth"), ("P570", "death"), ("P575", "discovered")):
        for c in claims.get(prop, []):
            t = c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("time", "")
            m = _re.match(r"[+-](\d{4})", str(t))
            if m:
                years[tag] = int(m.group(1))
                break
    if not years:
        return {}
    return {"label": hits[0].get("label", term),
            "description": hits[0].get("description", ""), "years": years}


def wikidata_year_flags(terms: list[str], script: str, max_flags: int = 3) -> list[str]:
    """Deterministic year cross-check (R&D 4.5): for each already-identified entity,
    flag script years WITHIN 2 of a Wikidata date but not equal to it - the classic
    LLM off-by-one date error. Exact matches and far-apart years pass silently.
    ADVISORY ONLY (Wikidata is crowd-edited): a flag is a prompt for the human at
    Gate 1, never an auto-block. Near-miss on an unrelated year is a possible false
    positive - hence the wording and the cap."""
    script_years = {int(y) for y in _re.findall(r"\b(1[0-9]{3}|20[0-9]{2})\b", script)}
    if not script_years:
        return []
    flags: list[str] = []
    for term in dict.fromkeys(t for t in terms if t.strip()):
        if len(flags) >= max_flags:
            break
        facts = wikidata_year_facts(term)
        for tag, year in (facts.get("years") or {}).items():
            if year in script_years:
                continue
            near = sorted(y for y in script_years if 0 < abs(y - year) <= 2)
            if near:
                flags.append(
                    f"Script mentions {near[0]}, but Wikidata has {facts['label']} "
                    f"{tag} = {year} ({facts.get('description', 'no description')}). "
                    "Verify which is right.")
    return flags[:max_flags]


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
