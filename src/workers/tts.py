"""TTS worker: narration text -> WAV via Kokoro on CPU (ADR-0009).

Measured on this box: ~2.8x realtime, so a 60s narration renders in ~20s.

2026-08-03 (R&D sections 5.2 + 5.3): synthesis is now PER SEGMENT (hook / each beat /
outro) with explicit inter-segment gaps, which yields exact per-beat timestamps as a
side effect - written to beat_timing.json next to the wav, and consumed by assemble
for beat-synced cuts. The Kokoro model is a module singleton (it used to reload the
ONNX file from disk on every call), and the raw synth is post-processed through the
ffmpeg voice chain (highpass / de-ess / compression / -16 LUFS).
"""

from __future__ import annotations

import json
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODEL = REPO_ROOT / "models" / "tts" / "kokoro-v1.0.onnx"
_VOICES = REPO_ROOT / "models" / "tts" / "voices-v1.0.bin"
DEFAULT_VOICE = "af_heart"
# Shorts pacing (R&D 5.2): slightly brisk delivery; per-video knob, judged at Gate 2.
DEFAULT_SPEED = 1.05
SEGMENT_GAP_S = 0.45  # breathing room between hook/beats/outro
TRIM_DB = -45.0  # edge-silence threshold
EDGE_PAD_S = 0.05

_kokoro = None


def _model():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro

        _kokoro = Kokoro(str(_MODEL), str(_VOICES))
    return _kokoro


def _trim_silence(samples, sr: int):
    """Cut leading/trailing silence, keeping a small pad so consonants never clip."""
    import numpy as np

    thresh = 10 ** (TRIM_DB / 20.0)
    loud = np.flatnonzero(np.abs(samples) > thresh)
    if loud.size == 0:
        return samples
    pad = int(EDGE_PAD_S * sr)
    lo = max(int(loud[0]) - pad, 0)
    hi = min(int(loud[-1]) + pad, len(samples))
    return samples[lo:hi]


def spec_segments(spec: dict) -> list[tuple[str, str]]:
    """The narration split assemble's cut logic mirrors: hook, each beat, payoff+cta."""
    segs = [("hook", spec["hook"])]
    segs += [(f"beat_{i}", b["narration"]) for i, b in enumerate(spec["beats"])]
    segs.append(("outro", (spec["payoff"] + " " + spec["cta"]).strip()))
    return [(label, text.strip()) for label, text in segs if text.strip()]


def render_narration_segments(segments: list[tuple[str, str]], out_path: str | pathlib.Path,
                              voice: str = DEFAULT_VOICE,
                              speed: float = DEFAULT_SPEED) -> tuple[float, list[dict]]:
    """Synthesize each (label, text) segment, join with gaps, run the voice chain.
    Writes out_path (48 kHz processed) + beat_timing.json + narration_raw.wav (pre-chain,
    kept for Gate 2 A/B). Returns (duration_s, timing list). Timings survive the voice
    chain untouched - nothing in it time-stretches."""
    import numpy as np
    import soundfile as sf

    from .audiofx import voice_chain

    kokoro = _model()
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    pieces: list = []
    timing: list[dict] = []
    cursor = 0.0
    sample_rate = 24000
    for i, (label, text) in enumerate(segments):
        samples, sample_rate = kokoro.create(text, voice=voice, speed=speed)
        samples = _trim_silence(np.asarray(samples), sample_rate)
        dur = len(samples) / sample_rate
        timing.append({"label": label, "start": round(cursor, 3), "end": round(cursor + dur, 3)})
        pieces.append(samples)
        cursor += dur
        if i < len(segments) - 1:
            pieces.append(np.zeros(int(SEGMENT_GAP_S * sample_rate), dtype=samples.dtype))
            cursor += SEGMENT_GAP_S

    joined = np.concatenate(pieces)
    raw = out.with_name("narration_raw.wav")
    sf.write(str(raw), joined, sample_rate)
    voice_chain(raw, out)
    (out.parent / "beat_timing.json").write_text(json.dumps(timing, indent=1), encoding="utf-8")
    info = sf.info(str(out))
    return info.frames / info.samplerate, timing


def render_narration(text: str, out_path: str | pathlib.Path, voice: str = DEFAULT_VOICE) -> float:
    """Single-shot synthesis (no beat timing) - kept for previews/tests."""
    import soundfile as sf

    samples, sample_rate = _model().create(text, voice=voice, speed=DEFAULT_SPEED)
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), samples, sample_rate)
    return len(samples) / sample_rate


def wav_to_mp3(wav_path: str | pathlib.Path) -> str:
    """Discord-playable mp3 preview next to the wav (raw WAV won't inline-play reliably)."""
    import subprocess

    from imageio_ffmpeg import get_ffmpeg_exe

    wav = pathlib.Path(wav_path)
    mp3 = wav.with_suffix(".mp3")
    subprocess.run(
        [get_ffmpeg_exe(), "-y", "-i", str(wav), "-codec:a", "libmp3lame", "-b:a", "128k", str(mp3)],
        capture_output=True, check=True,
    )
    return str(mp3)
