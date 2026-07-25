"""TTS worker: narration text -> WAV via Kokoro on CPU (ADR-0009).

Measured on this box: ~2.8x realtime, so a 60s narration renders in ~20s.
"""

from __future__ import annotations

import pathlib

_MODEL = "models/tts/kokoro-v1.0.onnx"
_VOICES = "models/tts/voices-v1.0.bin"
DEFAULT_VOICE = "af_heart"


def render_narration(text: str, out_path: str | pathlib.Path, voice: str = DEFAULT_VOICE) -> float:
    """Render text to out_path (24 kHz WAV). Returns audio duration in seconds."""
    import soundfile as sf
    from kokoro_onnx import Kokoro

    kokoro = Kokoro(_MODEL, _VOICES)
    samples, sample_rate = kokoro.create(text, voice=voice, speed=1.0)
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), samples, sample_rate)
    return len(samples) / sample_rate
