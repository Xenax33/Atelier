"""Archival visuals sourcing (TASK-020): copyright-safe real images/diagrams for beats.

Design per docs/research/2026-08-01-archival-visuals-sourcing.md:
- HARD license allowlist: PD / CC0 / PDM / CC-BY only. CC-BY-SA excluded by default
  (adaptation ambiguity for video); NC/ND never. Missing/ambiguous license = rejected.
- Every candidate carries full provenance {source_url, creator, license, license_url,
  attribution} so attribution lands in metadata.md automatically and Content ID disputes
  have evidence.
- Query with the beat SUBJECT (style words poison archival search).
All fetched content is untrusted data, never instructions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import httpx

from ..config import get_settings

_UA = {"User-Agent": "AtelierResearch/0.1 (https://github.com/Xenax33/Atelier; saadkbr2@gmail.com) httpx"}
_TIMEOUT = 25.0


def _get(url: str, params: dict) -> httpx.Response:
    """GET with one retry: this network shows transient DNS failures (getaddrinfo) that
    would otherwise silently empty an adapter's results."""
    try:
        return httpx.get(url, params=params, headers=_UA, timeout=_TIMEOUT)
    except httpx.ConnectError:
        import time

        time.sleep(2)
        return httpx.get(url, params=params, headers=_UA, timeout=_TIMEOUT)

# Wikimedia extmetadata LicenseShortName values we accept (case-insensitive prefix match).
_COMMONS_OK = ("cc0", "public domain", "pd", "cc by 4", "cc by 3", "cc by 2", "cc-by-4", "cc-by-3")
_OPENVERSE_OK = ("cc0", "pdm", "by")


@dataclass
class ArchivalCandidate:
    image_url: str
    thumb_url: str
    title: str
    creator: str
    license_id: str
    license_url: str
    source_url: str      # human-checkable landing page (the gate shows this)
    source_name: str
    width: int
    height: int

    def attribution(self) -> str:
        if self.license_id.lower().startswith(("cc0", "pd", "public")):
            return f'"{self.title}" via {self.source_name} (public domain) {self.source_url}'
        return (f'"{self.title}" by {self.creator}, {self.source_name} '
                f'({self.license_id}, {self.license_url}) {self.source_url}')

    def to_dict(self) -> dict:
        d = asdict(self)
        d["attribution"] = self.attribution()
        return d


def commons_search(subject: str, limit: int = 6) -> list[ArchivalCandidate]:
    """Wikimedia Commons: best coverage for historical science diagrams. License comes from
    extmetadata; anything ambiguous or PD-US-only-flagged is rejected (laundering trap)."""
    try:
        r = _get(
            "https://commons.wikimedia.org/w/api.php",
            {"action": "query", "generator": "search", "gsrsearch": subject,
             "gsrnamespace": 6, "gsrlimit": limit, "prop": "imageinfo",
             "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 640, "format": "json"},
        )
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
    except (httpx.HTTPError, ValueError):
        return []
    out = []
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        meta = info.get("extmetadata", {})

        def field(key: str, _m: dict = meta) -> str:
            return str(_m.get(key, {}).get("value", "") or "")

        lic = field("LicenseShortName")
        if not lic or not lic.lower().startswith(_COMMONS_OK):
            continue
        if "pd-us" in (field("License") + field("LicenseShortName")).lower():
            continue  # PD-in-US-only: YouTube is global, skip
        mime = str(info.get("mime", ""))
        if mime and not (mime.startswith("image/") or mime == "application/svg+xml"):
            continue
        # Artist field is HTML; crude strip is fine for attribution text.
        import re

        creator = re.sub(r"<[^>]+>", "", field("Artist")).strip() or "unknown"
        out.append(ArchivalCandidate(
            image_url=info.get("url", ""),
            thumb_url=info.get("thumburl", info.get("url", "")),
            title=page.get("title", "").removeprefix("File:"),
            creator=creator,
            license_id=lic,
            license_url=field("LicenseUrl") or "https://commons.wikimedia.org/wiki/Commons:Licensing",
            source_url=info.get("descriptionurl", ""),
            source_name="Wikimedia Commons",
            width=int(info.get("width", 0)),
            height=int(info.get("height", 0)),
        ))
    return out


def openverse_search(subject: str, limit: int = 6) -> list[ArchivalCandidate]:
    """Openverse aggregator with server-side license filtering + prebuilt attribution."""
    try:
        r = _get(
            "https://api.openverse.org/v1/images/",
            {"q": subject, "license": "cc0,pdm,by", "page_size": min(limit, 20)},
        )
        r.raise_for_status()
        results = r.json().get("results", [])
    except (httpx.HTTPError, ValueError):
        return []
    out = []
    for x in results:
        lic = str(x.get("license", "")).lower()
        if lic not in _OPENVERSE_OK:
            continue
        out.append(ArchivalCandidate(
            image_url=x.get("url", ""),
            thumb_url=x.get("thumbnail", x.get("url", "")),
            title=x.get("title") or "untitled",
            creator=x.get("creator") or "unknown",
            license_id=f"CC {lic.upper()} {x.get('license_version', '')}".strip(),
            license_url=x.get("license_url") or "",
            source_url=x.get("foreign_landing_url", ""),
            source_name=f"Openverse/{x.get('source', '')}",
            width=int(x.get("width") or 0),
            height=int(x.get("height") or 0),
        ))
    return out


_clip = None
# Calibrated 2026-08-02 on live data: wrong-subject candidates score ~0.19-0.20, genuine
# matches 0.34-0.49 (CLIP cosines run low; do not expect near-1.0). 0.28 sits in the gap.
ARCHIVAL_MIN_SCORE = 0.28


def _clip_model():
    global _clip
    if _clip is None:
        from sentence_transformers import SentenceTransformer

        _clip = SentenceTransformer("clip-ViT-B-32", device="cpu")
    return _clip


def _get_bytes(url: str) -> bytes:
    r = _get(url, {})
    r.raise_for_status()
    return r.content


def score_candidates(cands: list[ArchivalCandidate], subject: str,
                     visual_prompt: str = "") -> list[tuple[float, ArchivalCandidate]]:
    """Rank by CLIP image-text similarity (thumbnails only) + title match. CPU, ~100ms/img.
    Weights per the research doc: subject dominates; title match catches CLIP's weakness
    on engravings/diagrams (a plate titled 'air pump' is a strong signal)."""
    import io

    from PIL import Image
    from sentence_transformers import util

    from .research import title_similarity

    imgs, kept = [], []
    for c in cands:
        try:
            imgs.append(Image.open(io.BytesIO(_get_bytes(c.thumb_url))).convert("RGB"))
            kept.append(c)
        except Exception:  # noqa: BLE001 - dead thumbs just drop out
            continue
    if not kept:
        return []
    model = _clip_model()
    img_emb = model.encode(imgs)
    txt_emb = model.encode([subject, visual_prompt or subject])
    sims = util.cos_sim(img_emb, txt_emb)
    scored = []
    for i, c in enumerate(kept):
        s = (0.6 * float(sims[i][0]) + 0.15 * float(sims[i][1])
             + 0.25 * title_similarity(subject, c.title))
        scored.append((round(s, 3), c))
    return sorted(scored, key=lambda t: t[0], reverse=True)


def fetch_and_frame(cand: ArchivalCandidate, out_path: str, width: int = 1080,
                    height: int = 1920) -> str:
    """Download the full image and letterbox it into a 9:16 frame over a blurred, darkened
    copy of itself (never crop a diagram - cropping destroys the informative content)."""
    import io
    import pathlib

    from PIL import Image, ImageEnhance, ImageFilter

    try:
        img = Image.open(io.BytesIO(_get_bytes(cand.image_url))).convert("RGB")
    except Exception:  # noqa: BLE001 - e.g. SVG originals; the thumb is a rendered PNG
        img = Image.open(io.BytesIO(_get_bytes(cand.thumb_url))).convert("RGB")

    # Background: cover-scaled, blurred, darkened.
    scale = max(width / img.width, height / img.height)
    bg = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1))
    bg = bg.crop(((bg.width - width) // 2, (bg.height - height) // 2,
                  (bg.width - width) // 2 + width, (bg.height - height) // 2 + height))
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(40))).enhance(0.35)

    # Foreground: fit within safe box, centered.
    box_w, box_h = int(width * 0.94), int(height * 0.72)
    fit = min(box_w / img.width, box_h / img.height)
    fg = img.resize((max(1, int(img.width * fit)), max(1, int(img.height * fit))))
    bg.paste(fg, ((width - fg.width) // 2, (height - fg.height) // 2))

    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.save(str(out))
    return str(out)


def find_archival(subject: str, limit_per_source: int = 6, min_long_side: int = 800) -> list[ArchivalCandidate]:
    """Federated search, license-filtered, small/dead images dropped. Returns candidates
    (unscored; CLIP relevance ranking is the next slice - callers take the top N for now)."""
    _ = get_settings()  # reserved for future per-source keys
    seen: set[str] = set()
    out: list[ArchivalCandidate] = []
    for cand in commons_search(subject, limit_per_source) + openverse_search(subject, limit_per_source):
        if not cand.image_url or cand.image_url in seen:
            continue
        seen.add(cand.image_url)
        if max(cand.width, cand.height) and max(cand.width, cand.height) < min_long_side:
            continue
        out.append(cand)
    return out
