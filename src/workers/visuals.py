"""Visuals worker: per-beat SDXL stills via ComfyUI-Zluda, WITH GPU serialization.

THE VRAM RULE (docs/HARDWARE.md): the 8 GB card holds ONE heavy occupant. This module
owns the choreography: stop llama-server -> run ComfyUI -> render all stills -> stop
ComfyUI -> restart llama-server. Callers just call render_beat_stills().

House style (ADR-0008) is applied HERE via STYLE_PREFIX/NEGATIVE so agents never
handle style words and the look stays consistent across every beat and video.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import time
import urllib.parse

import httpx

COMFY_DIR = "F:\\ComfyUI-Zluda"
COMFY_BASE = "http://127.0.0.1:8188"
LLAMA_EXE = "bin\\llama-b10092\\llama-server.exe"
LLAMA_BASE = "http://127.0.0.1:8080"


def _brain_model(repo_root: pathlib.Path) -> pathlib.Path:
    """The brain GGUF from settings (BRAIN_MODEL_PATH in .env); relative to repo root.
    Configurable since 2026-08-08 for the Gemma 4 E4B A/B - gateway._ensure_brain and
    start-day.ps1 use the same source of truth."""
    from ..config import get_settings

    p = pathlib.Path(get_settings().brain_model_path)
    return p if p.is_absolute() else repo_root / p

# Smart-routing style presets (user decision 2026-08-02, amends ADR-0008): painterly for
# any scene with people (hides anatomy inconsistency, no realistic-person disclosure risk),
# cinematic semi-real only for people-free establishing shots. Subject stays FIRST in the
# prompt; style is a suffix (R&D: docs/research/2026-08-02-sdxl-vector-adherence.md).
STYLE_PRESETS = {
    "painterly": {
        "suffix": (", rich digital painting, storybook illustration, painterly brush strokes, "
                   "warm cinematic lighting, detailed environment, atmospheric depth"),
        "negative": "photo, photorealistic, 3d render, flat design, vector, blurry, text, numbers, watermark, deformed",
        "lora": 0.0,
        # ckpt per preset (R&D 1.1): ADOPTED 2026-08-08 same-seed A/B - DreamShaper renders
        # true painted light/texture where base gave flat comic outlines (and drops base's
        # fake storybook frame). Both checkpoints verified openrail++ (research doc section 9).
        "ckpt": "DreamShaperXL_1.0_fp16.safetensors",
    },
    "cinematic": {
        "suffix": (", cinematic film still, dramatic volumetric lighting, shallow depth of field, "
                   "highly detailed, moody atmosphere"),
        "negative": "cartoon, illustration, vector, flat design, anime, blurry, text, numbers, watermark, deformed, bad anatomy",
        "lora": 0.0,
        "ckpt": "RealVisXL_V5.0_fp16.safetensors",  # A/B 2026-08-08: photographic depth vs base's flat look
    },
    "vector": {  # retired default, kept selectable (DD LoRA was tuned on base - keep base here)
        "suffix": ", vector, complex details, outlines, flat design illustration, warm amber and deep navy palette, centered composition",
        "negative": "photo, photorealistic, 3d render, gradient, blurry, text, numbers, watermark, deformed",
        "lora": 0.65,
        "ckpt": "sd_xl_base_1.0.safetensors",
    },
}
DEFAULT_STYLE = "painterly"

# Warm renders are ~3-4 min, BUT a wiped MIOpen/ZLUDA cache forces a full kernel re-tune that
# can legitimately take 30-60 min (seen live 2026-08-02: ~/.miopen deleted, timeout killed a
# healthy compile). So: a big hard cap, plus liveness checks instead of impatience - we only
# give up early if the server dies or our job vanishes from the queue.
PER_IMAGE_TIMEOUT_S = 4500

# Sampler settings as module constants so tests can bisect crashes by overriding them.
SAMPLER_NAME = "dpmpp_2m"
SCHEDULER = "karras"
STEPS = 32
# PAG (Perturbed-Attention Guidance): structural-coherence fix, custom node
# sd-perturbed-attention in the ComfyUI-Zluda install. Paper values: CFG 4 + PAG 3.
USE_PAG = True
PAG_SCALE = 3.0
CFG = 4.0 if USE_PAG else 7.0
# AYS (R&D 1.2): ADOPTED 2026-08-08 after the same-seed A/B session - quality on par with
# 32/karras at 2.6x the speed (118s vs ~315s warm), verified on base AND on both production
# checkpoints. 10 steps was visibly flatter - keep 12. Composes with PAG (a model patch).
# Do NOT combine with distilled LoRAs.
USE_AYS = True
AYS_STEPS = 12
# Hires-fix (R&D 1.3): REJECTED as-shipped in the 2026-08-08 A/B - heavy horizontal
# smearing/ghosting across the whole frame (bislerp 1.5x + denoise 0.3 + tiled decode on
# this ZLUDA stack). Keep OFF; revisit with higher denoise (0.4-0.5) / different upscale
# method / non-tiled decode. The failed reference render: scratchpad ab/hires_painterly.
USE_HIRES = False
HIRES_W, HIRES_H = 1152, 2016
HIRES_STEPS = 12
HIRES_DENOISE = 0.3
# Guidance-alternative node ids, read from the INSTALLED pack's NODE_CLASS_MAPPINGS
# (2026-08-06, closes the TASK-035 identify-on-box TODO). NOTE: production PAG uses
# ComfyUI CORE's "PerturbedAttentionGuidance" (comfy_extras/nodes_pag.py); the pack's
# advanced variant is registered as plain "PerturbedAttention". For the future A/B:
#   SEG "SmoothedEnergyGuidanceAdvanced" (model, scale=3.0, blur_sigma=-1, unet_block=middle)
#   FDG "FrequencyDecoupledGuidance"     (model, strength_high=12.0)
#   NAG "NormalizedAttentionGuidance" | TPG "TokenPerturbationGuidance"
#   SWG "SlidingWindowGuidanceAdvanced"


def _pid_alive(pid: int) -> bool:
    r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                       capture_output=True, text=True, check=False)
    return str(pid) in (r.stdout or "")


def _up(url: str, timeout: float = 3.0) -> bool:
    try:
        return httpx.get(url, timeout=timeout).status_code == 200
    except httpx.HTTPError:
        return False


def _wait(url: str, timeout_s: int) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _up(url):
            return True
        time.sleep(5)
    return False


def stop_llama() -> None:
    subprocess.run(
        ["taskkill", "/IM", "llama-server.exe", "/F"],
        capture_output=True, check=False,
    )


def start_llama(repo_root: pathlib.Path) -> bool:
    if _up(LLAMA_BASE + "/health"):
        return True
    subprocess.Popen(
        [
            str(repo_root / LLAMA_EXE), "-m", str(_brain_model(repo_root)),
            "-ngl", "99", "-c", "16384", "-fa", "off", "--jinja",
            "--host", "127.0.0.1", "--port", "8080", "--threads", "6",
        ],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return _wait(LLAMA_BASE + "/health", 180)


def start_comfy() -> bool:
    if _up(COMFY_BASE + "/system_stats"):
        return True
    subprocess.Popen(
        ["cmd.exe", "/c", f"cd /d {COMFY_DIR} && {COMFY_DIR}\\comfyui-n.bat"],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return _wait(COMFY_BASE + "/system_stats", 420)


def stop_comfy() -> None:
    # Kill the ComfyUI process tree (python + zluda + cmd wrapper) by command-line match.
    ps = (
        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'ComfyUI-Zluda' "
        "-and $_.Name -match 'python|zluda|cmd' } | ForEach-Object { "
        "Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, check=False)


# DARK FLAG (R&D 6.4): release VRAM via POST /free instead of killing the process, keeping
# the ZLUDA init + warm MIOpen state alive across phases (saves minutes per phase switch
# and the Defender file-lock failure mode). torch's caching allocator may not return every
# MB to the OS, so the VRAM gate below is mandatory - on failure we fall back to the kill.
KEEP_COMFY_WARM = False
_LLAMA_NEEDS_VRAM_MB = 6000  # Qwen3-4B Q4 + KV headroom; the 8 GB card must free this much


def _free_comfy() -> bool:
    """Ask ComfyUI to unload models + GC, then verify enough VRAM actually came back.
    True = safe to start llama-server with the process still warm."""
    try:
        httpx.post(COMFY_BASE + "/free",
                   json={"unload_models": True, "free_memory": True}, timeout=30)
    except httpx.HTTPError:
        return False
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            stats = httpx.get(COMFY_BASE + "/system_stats", timeout=10).json()
            free_mb = min(d.get("vram_free", 0) for d in stats.get("devices", [{}])) / 2**20
            if free_mb >= _LLAMA_NEEDS_VRAM_MB:
                return True
        except (httpx.HTTPError, ValueError):
            return False
        time.sleep(3)
    return False


def _model_ref() -> list:
    """The model every sampler consumes: PAG patch when enabled, else the LoRA chain.
    A function (not a frozen constant) so test-time toggling of USE_PAG keeps working."""
    return ["pag", 0] if USE_PAG else ["lora", 0]


def _ays_nodes(seed: int) -> dict:
    """AYS first-pass via SamplerCustomAdvanced (R&D 1.2). Node keyed "sampler" so
    cudnn_off/hires wiring is identical to the KSampler path; output index 0 is the
    sampled latent (index 1 is denoised_output - unused). PAG composes unchanged."""
    return {
        "ays": {"class_type": "AlignYourStepsScheduler",
                "inputs": {"model_type": "SDXL", "steps": AYS_STEPS, "denoise": 1.0}},
        "ksel": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": SAMPLER_NAME}},
        "noise": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "guider": {"class_type": "CFGGuider", "inputs": {
            "model": _model_ref(), "positive": ["pos", 0], "negative": ["neg", 0], "cfg": CFG}},
        "sampler": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["noise", 0], "guider": ["guider", 0], "sampler": ["ksel", 0],
            "sigmas": ["ays", 0], "latent_image": ["latent", 0]}},
    }


def _workflow(visual_prompt: str, seed: int, style: str = DEFAULT_STYLE) -> dict:
    preset = STYLE_PRESETS.get(style, STYLE_PRESETS[DEFAULT_STYLE])
    return {
        "ckpt": {"class_type": "CheckpointLoaderSimple",
                 "inputs": {"ckpt_name": preset.get("ckpt", "sd_xl_base_1.0.safetensors")}},
        # Style LoRA (TASK-011): Doctor Diffusion Controllable Vector Art v2. Commercial-image
        # use allowed, trained on CC0 images (cleanest provenance found). Trigger word "vector"
        # is present in STYLE_PREFIX; control words: "simple details"/"complex details"/"outlines".
        "lora": {"class_type": "LoraLoader", "inputs": {
            "model": ["ckpt", 0], "clip": ["ckpt", 1],
            "lora_name": "DD-vector-v2.safetensors",
            "strength_model": preset["lora"], "strength_clip": preset["lora"]}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "sdxl_vae_fp16_fix.safetensors"}},
        "pos": {"class_type": "CLIPTextEncode",
                "inputs": {"text": visual_prompt + preset["suffix"], "clip": ["lora", 1]}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": preset["negative"], "clip": ["lora", 1]}},
        "latent": {"class_type": "EmptyLatentImage",
                   "inputs": {"width": 768, "height": 1344, "batch_size": 1}},
        # Quality settings per TASK-011 (user accepted longer renders): dpmpp_2m+karras at
        # 32 steps renders noticeably cleaner shapes/edges than euler/20 on SDXL base.
        **({"pag": {"class_type": "PerturbedAttentionGuidance",
                    "inputs": {"model": ["lora", 0], "scale": PAG_SCALE}}} if USE_PAG else {}),
        # First pass: classic KSampler, or the custom-sampler path with AYS sigmas (both
        # end in a node keyed "sampler" so the downstream wiring is identical).
        **(_ays_nodes(seed) if USE_AYS else {
            "sampler": {"class_type": "KSampler", "inputs": {
                "model": _model_ref(), "positive": ["pos", 0], "negative": ["neg", 0],
                "latent_image": ["latent", 0], "seed": seed, "steps": STEPS, "cfg": CFG,
                "sampler_name": SAMPLER_NAME, "scheduler": SCHEDULER, "denoise": 1.0}}}),
        # Optional hires second pass (R&D 1.3): 1.5x latent upscale + low-denoise refine.
        **({"hires_up": {"class_type": "LatentUpscale", "inputs": {
                "samples": ["sampler", 0], "upscale_method": "bislerp",
                "width": HIRES_W, "height": HIRES_H, "crop": "disabled"}},
            "hires_sampler": {"class_type": "KSampler", "inputs": {
                "model": _model_ref(), "positive": ["pos", 0], "negative": ["neg", 0],
                "latent_image": ["hires_up", 0], "seed": seed, "steps": HIRES_STEPS,
                "cfg": CFG, "sampler_name": SAMPLER_NAME, "scheduler": SCHEDULER,
                "denoise": HIRES_DENOISE}}} if USE_HIRES else {}),
        # RDNA1 fix: VAE decode dies with "GET was unable to find an engine" when cudnn is
        # enabled (documented in SETUP-COMFYUI.md). The CFZ toggle node disables cudnn and
        # passes the latent through; index 2 of its outputs is the latent.
        "cudnn_off": {"class_type": "CUDNNToggleAutoPassthrough", "inputs": {
            "latent": ["hires_sampler" if USE_HIRES else "sampler", 0],
            "enable_cudnn": False, "cudnn_benchmark": False}},
        # Tiled decode caps VAE VRAM at the hires resolution (the miopenStatusUnknownError
        # risk SETUP-COMFYUI warns about); plain decode stays for the unchanged 768x1344 path.
        "decode": ({"class_type": "VAEDecodeTiled", "inputs": {
                        "samples": ["cudnn_off", 2], "vae": ["vae", 0], "tile_size": 512,
                        "overlap": 64, "temporal_size": 64, "temporal_overlap": 8}}
                   if USE_HIRES else
                   {"class_type": "VAEDecode", "inputs": {"samples": ["cudnn_off", 2], "vae": ["vae", 0]}}),
        "save": {"class_type": "SaveImage",
                 "inputs": {"images": ["decode", 0], "filename_prefix": "atelier-run"}},
    }


def _render_one(visual_prompt: str, seed: int, out_file: pathlib.Path,
                style: str = DEFAULT_STYLE) -> None:
    r = httpx.post(COMFY_BASE + "/prompt",
                   json={"prompt": _workflow(visual_prompt, seed, style)}, timeout=30)
    r.raise_for_status()
    pid = r.json()["prompt_id"]
    deadline = time.time() + PER_IMAGE_TIMEOUT_S
    conn_failures = 0
    missing_from_queue = 0
    while time.time() < deadline:
        time.sleep(10)
        try:
            h = httpx.get(f"{COMFY_BASE}/history/{pid}", timeout=15).json()
            conn_failures = 0
        except httpx.HTTPError:
            conn_failures += 1
            if conn_failures >= 3:
                raise RuntimeError(
                    "ComfyUI process died mid-render (connection refused 3x). "
                    "Check F:\\ComfyUI-Zluda\\user\\comfyui.log for the crash point."
                ) from None
            continue
        entry = h.get(pid)
        if not entry:
            # Not finished yet: verify the job still EXISTS (running or pending). A long wait
            # with the job in-queue is a kernel compile, not a hang - keep waiting.
            try:
                q = httpx.get(f"{COMFY_BASE}/queue", timeout=15).json()
                ids = [item[1] for item in q.get("queue_running", []) + q.get("queue_pending", [])]
                missing_from_queue = 0 if pid in ids else missing_from_queue + 1
                if missing_from_queue >= 3:
                    raise RuntimeError("render job vanished from the ComfyUI queue without a result")
            except httpx.HTTPError:
                pass
            continue
        if not entry:
            continue
        status = entry.get("status", {})
        if status.get("status_str") == "error":
            raise RuntimeError(f"ComfyUI execution error: {json.dumps(status)[:500]}")
        if status.get("completed"):
            img = next(iter(entry["outputs"].values()))["images"][0]
            q = urllib.parse.urlencode(
                {"filename": img["filename"], "subfolder": img.get("subfolder", ""), "type": "output"}
            )
            data = httpx.get(f"{COMFY_BASE}/view?{q}", timeout=60).content
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_bytes(data)
            return
    # Hard cap reached: cancel the stuck job so teardown does not leave orphan queue work.
    try:
        httpx.post(f"{COMFY_BASE}/interrupt", timeout=10)
    except httpx.HTTPError:
        pass
    raise TimeoutError(
        f"image render exceeded {PER_IMAGE_TIMEOUT_S}s hard cap (job was interrupted). "
        "If kernel caches were wiped, the first render re-tunes for 30-60 min - see RUNBOOK."
    )


def render_beat_stills(prompts: list[str], run_assets_dir: str | pathlib.Path,
                       repo_root: str | pathlib.Path, base_seed: int = 1000,
                       indices: list[int] | None = None,
                       styles: list[str] | None = None) -> list[str]:
    """Render one still per beat prompt with full GPU choreography. Returns file paths.
    indices: beat numbers used for filenames (so archival beats can interleave).
    styles: per-prompt style preset names (smart routing); DEFAULT_STYLE when omitted."""
    assets = pathlib.Path(run_assets_dir)
    root = pathlib.Path(repo_root)
    idx = indices if indices is not None else list(range(len(prompts)))
    sty = styles if styles is not None else [DEFAULT_STYLE] * len(prompts)
    # Render lock, two jobs (both learned the hard way on 2026-08-04):
    # 1. Tells the AtelierWatchdog (start-day.ps1 -IfOn, every 5 min) that llama is down
    #    ON PURPOSE - without it the watchdog restarts the brain mid-render and SDXL
    #    loses half its VRAM (observed: 49-min beat renders).
    # 2. MUTEX between render drivers: two processes resuming the same run (bot + headless
    #    CLI, or a stale gate-button click) interleaved duplicate jobs in ComfyUI until the
    #    process died. A fresh lock owned by a LIVE other pid is a hard error.
    # Refreshed per image so a crashed render goes stale (>80 min) and unblocks everything.
    import os

    lock = root / "state" / ".render-lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    if lock.exists():
        age_min = (time.time() - lock.stat().st_mtime) / 60
        owner = (lock.read_text(encoding="ascii").split("|") + [""])[1]
        alive = owner.isdigit() and _pid_alive(int(owner))
        if age_min < 80 and alive and int(owner) != os.getpid():
            raise RuntimeError(
                f"another process (pid {owner}) is already rendering - refusing to "
                "double-drive the GPU. If that render is dead, delete state/.render-lock.")
    lock.write_text(f"{time.strftime('%Y-%m-%dT%H:%M:%S')}|{os.getpid()}", encoding="ascii")
    stop_llama()
    time.sleep(3)
    try:
        if not start_comfy():
            raise RuntimeError("ComfyUI failed to start (see docs/SETUP-COMFYUI.md)")
        paths = []
        for i, prompt, style in zip(idx, prompts, sty, strict=True):
            lock.write_text(f"{time.strftime('%Y-%m-%dT%H:%M:%S')}|{os.getpid()}",
                            encoding="ascii")
            out = assets / f"beat_{i:02d}.png"
            _render_one(prompt, base_seed + i, out, style)
            paths.append(str(out))
        return paths
    finally:
        lock.unlink(missing_ok=True)
        if not (KEEP_COMFY_WARM and _free_comfy()):
            stop_comfy()
        time.sleep(3)
        start_llama(root)
