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
LLAMA_MODEL = "models\\Qwen3-4B-Instruct-2507-UD-Q4_K_XL.gguf"
LLAMA_BASE = "http://127.0.0.1:8080"

STYLE_PREFIX = (
    "flat vector illustration, minimalist science-explainer style, clean geometric shapes, "
    "warm amber and deep navy palette, soft gradients, subtle paper texture, elegant "
    "editorial composition, strong single focal point, vertical composition, "
)
NEGATIVE = (
    "photo, photorealistic, 3d render, text, letters, watermark, signature, blurry, low quality, "
    "deformed, cluttered, messy lines, extra limbs, extra fingers, distorted face, low contrast"
)

PER_IMAGE_TIMEOUT_S = 1500  # warm ~3 min; first render of a session may recompile some kernels

# Sampler settings as module constants so tests can bisect crashes by overriding them.
SAMPLER_NAME = "dpmpp_2m"
SCHEDULER = "karras"
STEPS = 32
CFG = 6.5
LORA_STRENGTH = 0.8  # set to 0 to bypass the LoRA entirely


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
            str(repo_root / LLAMA_EXE), "-m", str(repo_root / LLAMA_MODEL),
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


def _workflow(visual_prompt: str, seed: int) -> dict:
    return {
        "ckpt": {"class_type": "CheckpointLoaderSimple",
                 "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
        # Style LoRA (TASK-011): Doctor Diffusion Controllable Vector Art v2. Commercial-image
        # use allowed, trained on CC0 images (cleanest provenance found). Trigger word "vector"
        # is present in STYLE_PREFIX; control words: "simple details"/"complex details"/"outlines".
        "lora": {"class_type": "LoraLoader", "inputs": {
            "model": ["ckpt", 0], "clip": ["ckpt", 1],
            "lora_name": "DD-vector-v2.safetensors",
            "strength_model": LORA_STRENGTH, "strength_clip": LORA_STRENGTH}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "sdxl_vae_fp16_fix.safetensors"}},
        "pos": {"class_type": "CLIPTextEncode",
                "inputs": {"text": STYLE_PREFIX + visual_prompt, "clip": ["lora", 1]}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE, "clip": ["lora", 1]}},
        "latent": {"class_type": "EmptyLatentImage",
                   "inputs": {"width": 768, "height": 1344, "batch_size": 1}},
        # Quality settings per TASK-011 (user accepted longer renders): dpmpp_2m+karras at
        # 32 steps renders noticeably cleaner shapes/edges than euler/20 on SDXL base.
        "sampler": {"class_type": "KSampler", "inputs": {
            "model": ["lora", 0], "positive": ["pos", 0], "negative": ["neg", 0],
            "latent_image": ["latent", 0], "seed": seed, "steps": STEPS, "cfg": CFG,
            "sampler_name": SAMPLER_NAME, "scheduler": SCHEDULER, "denoise": 1.0}},
        # RDNA1 fix: VAE decode dies with "GET was unable to find an engine" when cudnn is
        # enabled (documented in SETUP-COMFYUI.md). The CFZ toggle node disables cudnn and
        # passes the latent through; index 2 of its outputs is the latent.
        "cudnn_off": {"class_type": "CUDNNToggleAutoPassthrough", "inputs": {
            "latent": ["sampler", 0], "enable_cudnn": False, "cudnn_benchmark": False}},
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["cudnn_off", 2], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage",
                 "inputs": {"images": ["decode", 0], "filename_prefix": "atelier-run"}},
    }


def _render_one(visual_prompt: str, seed: int, out_file: pathlib.Path) -> None:
    r = httpx.post(COMFY_BASE + "/prompt", json={"prompt": _workflow(visual_prompt, seed)}, timeout=30)
    r.raise_for_status()
    pid = r.json()["prompt_id"]
    deadline = time.time() + PER_IMAGE_TIMEOUT_S
    conn_failures = 0
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
    raise TimeoutError(f"image render exceeded {PER_IMAGE_TIMEOUT_S}s")


def render_beat_stills(prompts: list[str], run_assets_dir: str | pathlib.Path,
                       repo_root: str | pathlib.Path, base_seed: int = 1000) -> list[str]:
    """Render one still per beat prompt with full GPU choreography. Returns file paths."""
    assets = pathlib.Path(run_assets_dir)
    root = pathlib.Path(repo_root)
    stop_llama()
    time.sleep(3)
    if not start_comfy():
        start_llama(root)
        raise RuntimeError("ComfyUI failed to start (see docs/SETUP-COMFYUI.md)")
    try:
        paths = []
        for i, prompt in enumerate(prompts):
            out = assets / f"beat_{i:02d}.png"
            _render_one(prompt, base_seed + i, out)
            paths.append(str(out))
        return paths
    finally:
        stop_comfy()
        time.sleep(3)
        start_llama(root)
