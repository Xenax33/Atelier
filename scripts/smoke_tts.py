"""Smoke test for Kokoro TTS (CPU): render a ~60-second narration and measure the real-time factor.

Usage (from repo root, inside .venv):
    python scripts/smoke_tts.py [--voice af_heart] [--out state/smoke/kokoro-smoke.wav]
Exit code 0 = wav written and RTF measured.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time

# A ~150-word science-history narration, the realistic pipeline payload.
NARRATION = (
    "In the spring of 1820, a Danish professor named Hans Christian Oersted was in the middle "
    "of a lecture when he noticed something odd. A compass needle sitting near his equipment "
    "twitched every time he switched the electric current on. Electricity was not supposed to "
    "do that. Magnetism and electricity were thought to be entirely separate forces of nature. "
    "But that trembling needle said otherwise. Oersted spent the next three months repeating "
    "the experiment in every configuration he could devise, and in July he published a short "
    "paper, barely four pages long, that set European physics on fire. Within weeks, Ampere "
    "had worked out the mathematics. Within five years, the first electromagnet was lifting "
    "iron. Within a generation, telegraph wires were carrying messages across continents. "
    "All of it traced back to one distracted moment in a Copenhagen lecture hall, and one "
    "professor who paid attention to a twitch."
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="af_heart")
    ap.add_argument("--out", default="state/smoke/kokoro-smoke.wav")
    ap.add_argument("--model", default="models/tts/kokoro-v1.0.onnx")
    ap.add_argument("--voices", default="models/tts/voices-v1.0.bin")
    args = ap.parse_args()

    import soundfile as sf
    from kokoro_onnx import Kokoro

    t0 = time.time()
    kokoro = Kokoro(args.model, args.voices)
    load_s = time.time() - t0

    t0 = time.time()
    samples, sample_rate = kokoro.create(NARRATION, voice=args.voice, speed=1.0)
    synth_s = time.time() - t0

    audio_s = len(samples) / sample_rate
    rtf = audio_s / synth_s if synth_s > 0 else 0

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), samples, sample_rate)

    print(f"[ok] model load: {load_s:.1f}s")
    print(f"[ok] synthesized {audio_s:.1f}s of audio in {synth_s:.1f}s  (RTF {rtf:.1f}x realtime)")
    print(f"[ok] voice={args.voice} sample_rate={sample_rate} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
