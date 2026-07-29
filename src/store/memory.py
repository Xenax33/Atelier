"""Production/episodic memory (ADR-0010 tier 1): what the channel has already made.

sqlite-vec table inside atelier.db + bge-small embeddings on CPU (~130MB, lazy-loaded).
Used for topic dedup at ideation time; grows into fact-consistency memory later.
NOT the taste model - that lives in prompts/editorial-profile.md (do not conflate).
"""

from __future__ import annotations

import pathlib
import sqlite3
import struct

from ..config import get_settings

_DIM = 384  # bge-small-en-v1.5
_model = None


def _embed(text: str) -> bytes:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
    vec = _model.encode([text], normalize_embeddings=True)[0]
    return struct.pack(f"{_DIM}f", *vec)


def _conn() -> sqlite3.Connection:
    import sqlite_vec

    conn = sqlite3.connect(get_settings().db_path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS topics(id INTEGER PRIMARY KEY, run_id TEXT UNIQUE, "
        "title TEXT, topic TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_topics USING vec0(id INTEGER PRIMARY KEY, "
        f"embedding float[{_DIM}])"
    )
    return conn


def remember_video(run_id: str, title: str, topic: str) -> None:
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO topics(run_id, title, topic) VALUES (?, ?, ?)",
            (run_id, title, topic),
        )
        if cur.rowcount:
            row_id = cur.lastrowid
            conn.execute(
                "INSERT INTO vec_topics(id, embedding) VALUES (?, ?)",
                (row_id, _embed(f"{title}. {topic}")),
            )
        conn.commit()
    finally:
        conn.close()


def similar_topics(text: str, k: int = 3) -> list[tuple[str, float]]:
    """[(title, L2_distance)] of the k nearest produced videos. Empty store -> [].

    NOTE: vec0 MATCH returns L2 distance; on normalized embeddings L2^2 = 2 - 2*cos_sim.
    Measured on real runs: same-topic paraphrase ~0.67, unrelated science topic ~0.96."""
    conn = _conn()
    try:
        if not conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0]:
            return []
        rows = conn.execute(
            "SELECT t.title, v.distance FROM vec_topics v JOIN topics t ON t.id = v.id "
            "WHERE v.embedding MATCH ? AND v.k = ? ORDER BY v.distance",
            (_embed(text), k),
        ).fetchall()
        return [(r[0], r[1]) for r in rows]
    finally:
        conn.close()


def is_duplicate(text: str, threshold: float = 0.85) -> tuple[bool, str]:
    """L2 distance < threshold counts as 'we already made this'.

    Calibrated on real runs (bge-small, short title texts): same-topic paraphrases measure
    0.67-0.78, unrelated science topics 0.94+. 0.85 sits in the gap. Re-check the bands if
    the embedding model changes."""
    near = similar_topics(text, k=1)
    if near and near[0][1] < threshold:
        return True, near[0][0]
    return False, ""


def backfill_from_runs() -> int:
    """Index pre-memory runs from their metadata files. Idempotent."""
    count = 0
    for meta in pathlib.Path("state/runs").glob("*/metadata.md"):
        try:
            title = meta.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
        except (OSError, IndexError):
            continue
        remember_video(meta.parent.name, title, title)
        count += 1
    return count
