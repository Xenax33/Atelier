"""Validate config/pronunciation_lexicon.json before trusting it in production.

Two failure modes this catches (R&D 2026-08-03, 5.1):
  1. A phoneme character that is NOT in Kokoro's vocab - the tokenizer drops unknown
     phonemes SILENTLY, so a typo'd entry would make the word partially vanish.
  2. misaki not honoring the inline override (syntax slip in the entry).

Usage:  python scripts/check_lexicon.py            (venv; needs misaki installed)
Exit 0 = every entry safe.
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def main() -> int:
    from kokoro_onnx.config import DEFAULT_VOCAB
    from src.workers.tts import LEXICON_PATH, _load_lexicon

    lex = _load_lexicon()
    if not lex:
        print(f"[FAIL] no entries loaded from {LEXICON_PATH}")
        return 1

    try:
        from misaki import en

        g2p = en.G2P(trf=False, british=False, fallback=None)
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] misaki unavailable ({e}) - lexicon would be dead weight")
        return 1

    failures = 0
    for word, phonemes in lex.items():
        bad_chars = sorted({c for c in phonemes if c not in DEFAULT_VOCAB})
        if bad_chars:
            print(f"[FAIL] {word}: chars not in Kokoro vocab (would be SILENTLY dropped): {bad_chars}")
            failures += 1
            continue
        ps, _tokens = g2p(f"[{word}](/{phonemes}/)")
        if phonemes not in ps:
            print(f"[FAIL] {word}: override not honored by misaki (got: {ps!r})")
            failures += 1
            continue
        print(f"[ok] {word} -> /{phonemes}/")

    if failures:
        print(f"\nRESULT: {failures} bad entrie(s) - fix before committing")
        return 1
    print(f"\nRESULT: all {len(lex)} entries safe (chars in vocab, overrides honored)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
