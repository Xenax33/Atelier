"""Smoke test for the visuals engine (ComfyUI-Zluda + SDXL on the RX 5700 XT).

Queues a single 768x1344 (9:16) SDXL txt2img via the ComfyUI API and waits for it,
reporting wall time. First run on ZLUDA compiles kernels: expect 10-20+ minutes; later
runs show the real per-image cost.

Stdlib only. Usage:
    python scripts/smoke_sdxl.py [--base http://127.0.0.1:8188] [--timeout 2400] [--tiled-vae]
Exit 0 = image rendered.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

PROMPT = (
    "flat vector illustration, 1820 physics lecture hall, scientist in period clothing "
    "observing a trembling compass needle beside a battery and wire, warm amber palette, "
    "clean geometric shapes, minimalist science-explainer style, vertical composition"
)
NEGATIVE = "photo, photorealistic, text, watermark, signature, blurry, low quality"


def build_workflow(tiled: bool) -> dict:
    wf = {
        "ckpt": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"},
        },
        "vae": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "sdxl_vae_fp16_fix.safetensors"},
        },
        "pos": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": PROMPT, "clip": ["ckpt", 1]},
        },
        "neg": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": NEGATIVE, "clip": ["ckpt", 1]},
        },
        "latent": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 768, "height": 1344, "batch_size": 1},
        },
        "sampler": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["ckpt", 0],
                "positive": ["pos", 0],
                "negative": ["neg", 0],
                "latent_image": ["latent", 0],
                "seed": 42,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            },
        },
        "save": {
            "class_type": "SaveImage",
            "inputs": {"images": ["decode", 0], "filename_prefix": "atelier-smoke"},
        },
    }
    if tiled:
        wf["decode"] = {
            "class_type": "VAEDecodeTiled",
            "inputs": {"samples": ["sampler", 0], "vae": ["vae", 0], "tile_size": 512},
        }
    else:
        wf["decode"] = {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["sampler", 0], "vae": ["vae", 0]},
        }
    return wf


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8188")
    ap.add_argument("--timeout", type=float, default=2400.0)
    ap.add_argument("--tiled-vae", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    base = args.base.rstrip("/")

    wf = build_workflow(args.tiled_vae)
    wf["sampler"]["inputs"]["seed"] = args.seed
    body = json.dumps({"prompt": wf}).encode()
    req = urllib.request.Request(
        base + "/prompt", data=body, headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        print(f"[FAIL] queue rejected: {e.read().decode()[:1000]}")
        return 1
    pid = resp["prompt_id"]
    print(f"[ok] queued prompt {pid} (tiled_vae={args.tiled_vae}); waiting (first ZLUDA run compiles, be patient)...")

    while time.time() - t0 < args.timeout:
        time.sleep(10)
        try:
            with urllib.request.urlopen(base + f"/history/{pid}", timeout=15) as r:
                hist = json.load(r)
        except urllib.error.URLError:
            continue
        if pid not in hist:
            continue
        entry = hist[pid]
        status = entry.get("status", {})
        if status.get("completed"):
            dt = time.time() - t0
            outputs = entry.get("outputs", {})
            files = [
                img["filename"]
                for node in outputs.values()
                for img in node.get("images", [])
            ]
            print(f"[ok] IMAGE RENDERED in {dt/60:.1f} min: {files}")
            print("     (output dir: F:\\ComfyUI-Zluda\\output)")
            return 0
        if status.get("status_str") == "error":
            msgs = [
                m for m in status.get("messages", [])
                if m and m[0] == "execution_error"
            ]
            detail = msgs[-1][1].get("exception_message", "?") if msgs else "?"
            print(f"[FAIL] execution error after {(time.time()-t0)/60:.1f} min: {detail[:800]}")
            return 1
    print(f"[FAIL] timed out after {args.timeout/60:.0f} min (queue may still be running)")
    return 2


if __name__ == "__main__":
    sys.exit(main())
