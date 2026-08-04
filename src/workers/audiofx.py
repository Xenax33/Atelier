"""Audio post-production via the bundled ffmpeg (imageio_ffmpeg - has loudnorm,
deesser, sidechaincompress compiled in; verified 2026-08-03).

Two jobs (docs/research/2026-08-03-pipeline-rnd.md sections 3.3 + 5.3):
  - voice_chain(): clean up raw TTS (highpass, de-ess, gentle compression, -16 LUFS).
  - build_final_audio(): optional music bed ducked under the voice via sidechain
    compression, then two-pass loudnorm to YouTube's -14 LUFS so upload re-gain
    never touches the mix.

Loudnorm is always TWO-PASS (measure, then linear correction with the measured
values): one-pass loudnorm falls back to dynamic mode, which pumps.
"""

from __future__ import annotations

import json
import pathlib
import random
import re
import subprocess

MUSIC_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
# Music bed level BEFORE ducking; sidechain then rides it further down under speech.
MUSIC_VOLUME = 0.30
DUCK = "sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400"
VOICE_LUFS = -16.0  # pre-mix headroom; the final mix lands at -14
MIX_LUFS = -14.0


def _ffmpeg() -> str:
    from imageio_ffmpeg import get_ffmpeg_exe

    return get_ffmpeg_exe()


def _run(args: list[str]) -> subprocess.CompletedProcess:
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({args[1:3]}...): {p.stderr[-800:]}")
    return p


def _measure_loudnorm(inputs: list[str], filter_prefix: str, target_i: float) -> dict:
    """Pass 1: run the chain with loudnorm in analysis mode, parse the JSON stats block."""
    ln = f"loudnorm=I={target_i}:TP=-1.5:LRA=11:print_format=json"
    chain = f"{filter_prefix}{ln}" if filter_prefix else ln
    args = [_ffmpeg(), "-hide_banner", "-y", *inputs]
    if "[" in chain:  # filter_complex graph (multiple inputs)
        args += ["-filter_complex", chain]
    else:
        args += ["-af", chain]
    args += ["-f", "null", "-"]
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.DOTALL)
    if p.returncode != 0 or not m:
        raise RuntimeError(f"loudnorm measure pass failed: {p.stderr[-800:]}")
    return json.loads(m.group(0))


def _loudnorm_pass2(measured: dict, target_i: float) -> str:
    return (
        f"loudnorm=I={target_i}:TP=-1.5:LRA=11:linear=true"
        f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
        f":offset={measured['target_offset']}"
    )


def voice_chain(wav_in: str | pathlib.Path, wav_out: str | pathlib.Path) -> str:
    """Raw TTS -> broadcast-ish narration: rumble filter, de-ess, gentle 3:1 glue,
    -16 LUFS. No time-stretching anywhere, so word/beat timings stay valid."""
    pre = "highpass=f=80,deesser,acompressor=threshold=-20dB:ratio=3:attack=5:release=150,"
    measured = _measure_loudnorm(["-i", str(wav_in)], pre, VOICE_LUFS)
    _run([_ffmpeg(), "-hide_banner", "-y", "-i", str(wav_in),
          "-af", pre + _loudnorm_pass2(measured, VOICE_LUFS),
          "-ar", "48000", str(wav_out)])
    return str(wav_out)


def pick_music(music_dir: str | pathlib.Path, seed: str = "") -> str | None:
    """Deterministic per-run pick from the local music folder (empty/missing -> None).
    Tracks come from the YouTube Audio Library / Kevin MacLeod (see assets/music/README.md);
    CC-BY tracks need the credit line in the video description."""
    d = pathlib.Path(music_dir)
    if not d.is_dir():
        return None
    tracks = sorted(p for p in d.iterdir() if p.suffix.lower() in MUSIC_EXTS)
    if not tracks:
        return None
    return str(random.Random(seed or None).choice(tracks))


def build_final_audio(voice_wav: str | pathlib.Path, out_wav: str | pathlib.Path,
                      music_path: str | None, duration_s: float) -> str:
    """Final mixed track at -14 LUFS. With music: bed trimmed/looped to length,
    ducked under the voice, mixed, normalized. Without: voice alone normalized."""
    voice, out = str(voice_wav), str(out_wav)
    if not music_path:
        measured = _measure_loudnorm(["-i", voice], "", MIX_LUFS)
        _run([_ffmpeg(), "-hide_banner", "-y", "-i", voice,
              "-af", _loudnorm_pass2(measured, MIX_LUFS), "-ar", "48000", out])
        return out
    inputs = ["-i", voice, "-stream_loop", "-1", "-i", music_path]
    # [music] trim to video length + fade out; duck against the voice; mix (normalize=0
    # keeps absolute levels so the sidechain ratio survives); loudnorm the MIX.
    prefix = (
        f"[1:a]atrim=0:{duration_s:.3f},volume={MUSIC_VOLUME},afade=t=out:st={max(duration_s - 1.5, 0):.3f}:d=1.5[m];"
        f"[m][0:a]{DUCK}[duck];"
        f"[0:a][duck]amix=inputs=2:duration=first:normalize=0,"
    )
    measured = _measure_loudnorm(inputs, prefix, MIX_LUFS)
    _run([_ffmpeg(), "-hide_banner", "-y", *inputs,
          "-filter_complex", prefix + _loudnorm_pass2(measured, MIX_LUFS),
          "-ar", "48000", out])
    return out
