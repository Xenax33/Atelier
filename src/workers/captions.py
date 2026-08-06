"""Captions worker: WAV -> word-level timestamps via faster-whisper on CPU.

We know the narration text already (we wrote it), so whisper here is used for TIMING,
not content. v1 upgrades to whisperx forced alignment against the known script.
First call downloads the model (~150 MB) into the HF cache.
"""

from __future__ import annotations

import json
import pathlib


def word_timestamps(audio_path: str | pathlib.Path, out_json: str | pathlib.Path) -> list[dict]:
    from faster_whisper import WhisperModel

    model = WhisperModel("base.en", device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(audio_path), word_timestamps=True, language="en")
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)})
    out = pathlib.Path(out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(words, indent=1), encoding="utf-8")
    return words


def _norm(word: str) -> str:
    import re

    return re.sub(r"[^a-z0-9']", "", word.lower())


def align_to_script(script_text: str, asr_words: list[dict]) -> list[dict]:
    """Burned-caption text from the KNOWN script; ASR supplies timing only (R&D 7.3).
    The pipeline wrote the script, so ASR misspellings of exactly the words this channel
    lives on (Lavoisier, Roentgen...) must never reach the screen. difflib alignment on
    normalized tokens: matched words take the ASR timing; substituted runs split the ASR
    span by word length; script words whisper missed squeeze into the adjacent gap; ASR
    hallucinations are dropped. Falls back to the ASR words if the script is empty."""
    import difflib

    script_words = script_text.split()
    if not script_words or not asr_words:
        return asr_words
    sm = difflib.SequenceMatcher(
        None, [_norm(w) for w in script_words], [_norm(w["word"]) for w in asr_words],
        autojunk=False)
    out: list[dict] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "insert":  # ASR-only tokens (hallucination/split) - timing absorbed below
            continue
        if tag == "equal":
            for k in range(i2 - i1):
                a = asr_words[j1 + k]
                out.append({"word": script_words[i1 + k], "start": a["start"], "end": a["end"]})
            continue
        # replace/delete: distribute a real time span across the script words by length.
        if tag == "replace" and j2 > j1:
            span_start, span_end = asr_words[j1]["start"], asr_words[j2 - 1]["end"]
        else:  # delete: whisper skipped these - use the gap between the neighbours
            span_start = out[-1]["end"] if out else 0.0
            span_end = asr_words[j2]["start"] if j2 < len(asr_words) else max(
                span_start, asr_words[-1]["end"])
        span_end = max(span_end, span_start)
        chunk = script_words[i1:i2]
        weights = [max(len(_norm(w)), 1) for w in chunk]
        edges = [span_start]
        for w in weights:
            edges.append(edges[-1] + (span_end - span_start) * w / sum(weights))
        for k, w in enumerate(chunk):
            out.append({"word": w, "start": round(edges[k], 3), "end": round(edges[k + 1], 3)})
    # Monotonic guard: overlaps confuse the karaoke sweep; clamp starts forward only.
    for prev, cur in zip(out, out[1:], strict=False):
        if cur["start"] < prev["end"]:
            cur["start"] = prev["end"]
            cur["end"] = max(cur["end"], cur["start"])
    return out
