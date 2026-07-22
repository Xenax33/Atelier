"""workers/ - deterministic (non-LLM) pipeline stages.

tts (Kokoro CPU / Orpheus Vulkan), captions (whisperX), visuals (SDXL via ComfyUI + Depth-Anything
parallax), manim (diagrams), assemble (ffmpeg/MoviePy 9:16 master + proxy), publish (private-draft upload).

VRAM rule: the heavy GPU workers (SDXL, GPU-whisper, Orpheus) must be SERIALIZED - never co-resident on
the 8 GB card. The graph enforces ordering; workers health-gate the GPU before starting. See docs/HARDWARE.md.
"""
