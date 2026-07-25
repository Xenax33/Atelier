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
