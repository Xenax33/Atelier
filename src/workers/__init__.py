"""workers/ - deterministic (non-LLM) pipeline stages.

Implemented: tts (Kokoro CPU + mp3 previews), captions (faster-whisper word timestamps),
visuals (SDXL via ComfyUI-Zluda with full GPU choreography incl. stopping/restarting the
llama brain), assemble (MoviePy/ffmpeg 9:16 faststart master + sub-10MB proxy, wrapped
burned captions, Ken-Burns). Planned: manim diagrams, archival-image compositor (TASK-020).

VRAM rule: heavy GPU stages (the in-VRAM brain, SDXL, GPU-whisper) must be SERIALIZED - never
co-resident on the 8 GB card. visuals.render_beat_stills owns the choreography. See docs/HARDWARE.md.
"""
