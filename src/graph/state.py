"""Shared pipeline state for one short (one LangGraph thread per video).

The spec dict is the contract between the Scriptwriter and every downstream worker
(see docs/ARCHITECTURE.md section 5). Everything here must be JSON-serializable so
SqliteSaver can checkpoint it and a future session can resume it.
"""

from __future__ import annotations

from typing import TypedDict


class Beat(TypedDict):
    narration: str      # 1-2 spoken sentences for this beat
    caption: str        # short on-screen caption text (not the narration transcript)
    visual_prompt: str  # SDXL prompt for this beat's still, house style applied downstream


class ShortSpec(TypedDict):
    title: str          # YouTube title suggestion
    hook: str           # spoken opening line, must grab in <=2s of speech
    beats: list[Beat]
    payoff: str         # spoken resolution that keeps the hook's promise
    cta: str            # one soft call-to-action line
    description: str    # YouTube description suggestion
    hashtags: list[str]


class ShortState(TypedDict, total=False):
    run_id: str
    topic: str
    evidence: list[dict]        # research pack: [{source, title, text}]
    claims: list[dict]          # fact-check audit: [{claim, verdict, evidence_ref}]
    spec: ShortSpec
    script_feedback: str        # user's regen feedback from Gate 1
    script_attempts: int
    narration_text: str         # full spoken text assembled from the spec
    audio_path: str
    audio_seconds: float
    image_paths: list[str]      # one still per beat, ordered
    words_path: str             # word-timestamps json from faster-whisper
    master_path: str
    proxy_path: str
    metadata_path: str
    error: str
