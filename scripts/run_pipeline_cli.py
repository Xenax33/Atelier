"""CLI driver for the pipeline: run a short end-to-end WITHOUT Discord, auto-approving
gates (or stopping at one). This is the MVP integration test and the resume-proof harness.

Usage (venv, repo root):
    python -m scripts.run_pipeline_cli --topic "Oersted's compass" [--run-id oersted-1]
        [--stop-after script|audio|final]   # leave that gate open and exit (for resume tests)
        [--resume RUN_ID]                   # resume an open gate with approval
"""

from __future__ import annotations

import argparse
import json
import time
import uuid

from langgraph.types import Command
from src.graph.build import get_graph


def show_interrupt(chunk: dict) -> dict | None:
    intr = chunk.get("__interrupt__")
    if not intr:
        return None
    payload = intr[0].value
    print(f"\n=== GATE: {payload.get('stage')} ===")
    if payload.get("stage") == "script":
        spec = payload["spec"]
        print(f"title: {spec['title']}\nhook:  {spec['hook']}")
        for i, b in enumerate(spec["beats"]):
            print(f"beat {i}: {b['narration']}")
        print(f"payoff: {spec['payoff']}\ncta: {spec['cta']}")
        words = len(" ".join([spec["hook"]] + [b["narration"] for b in spec["beats"]]
                             + [spec["payoff"], spec["cta"]]).split())
        print(f"[{words} spoken words]")
    else:
        print(json.dumps(payload, indent=1)[:400])
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic")
    ap.add_argument("--run-id")
    ap.add_argument("--stop-after", choices=["script", "audio", "final"])
    ap.add_argument("--resume", help="resume this run id with an approval")
    args = ap.parse_args()

    graph = get_graph()

    if args.resume:
        cfg = {"configurable": {"thread_id": args.resume}}
        print(f"resuming {args.resume} with approve...")
        result = graph.invoke(Command(resume={"action": "approve"}), cfg)
    else:
        if not args.topic:
            ap.error("--topic required for a new run")
        run_id = args.run_id or f"{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
        cfg = {"configurable": {"thread_id": run_id}}
        print(f"run_id/thread_id: {run_id}")
        result = graph.invoke({"run_id": run_id, "topic": args.topic}, cfg)

    while True:
        payload = show_interrupt(result)
        if payload is None:
            break
        stage = payload.get("stage")
        if args.stop_after == stage:
            print(f"stopping with the {stage} gate OPEN (resume later with --resume)")
            return
        print(f"auto-approving {stage} gate...")
        result = graph.invoke(Command(resume={"action": "approve"}), cfg)

    print("\n=== PIPELINE FINISHED ===")
    for k in ("audio_path", "audio_seconds", "image_paths", "master_path", "proxy_path",
              "metadata_path", "error"):
        if k in result:
            print(f"{k}: {result[k]}")


if __name__ == "__main__":
    main()
