"""Smoke test for the model gateway (llama-server, OpenAI-compatible API).

Checks the three behaviors the pipeline lives on:
  1. /health and /v1/models respond.
  2. Schema-constrained JSON: response_format json_schema yields parseable, schema-shaped output.
  3. Tool-calling: the model emits a well-formed tool_call for an obvious tool task.

Stdlib only (no venv needed). Usage:
    python scripts/smoke_llm.py [--base http://127.0.0.1:8080] [--timeout 120]
Exit code 0 = all pass.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "hook": {"type": "string", "description": "opening line, 12 words max"},
        "beats": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {"type": "string"},
        },
    },
    "required": ["topic", "hook", "beats"],
    "additionalProperties": False,
}

WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "lookup_source",
        "description": "Look up a scientific source by DOI and return its title and year.",
        "parameters": {
            "type": "object",
            "properties": {"doi": {"type": "string", "description": "the DOI to resolve"}},
            "required": ["doi"],
        },
    },
}


def post(base: str, path: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def get(base: str, path: str, timeout: float) -> dict:
    with urllib.request.urlopen(base + path, timeout=timeout) as resp:
        return json.load(resp)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8080")
    ap.add_argument("--timeout", type=float, default=120.0)
    args = ap.parse_args()
    base = args.base.rstrip("/")
    failures = []

    # 1. health + model id
    try:
        get(base, "/health", args.timeout)
        models = get(base, "/v1/models", args.timeout)
        model_id = models["data"][0]["id"]
        print(f"[ok] server healthy, model: {model_id}")
    except (urllib.error.URLError, KeyError, IndexError) as e:
        print(f"[FAIL] server not reachable/healthy: {e}")
        return 1

    # 2. schema-constrained JSON
    t0 = time.time()
    try:
        r = post(base, "/v1/chat/completions", {
            "model": model_id,
            "messages": [
                {"role": "system", "content": "You draft 60-second science-history shorts."},
                {"role": "user", "content": "Draft a spec for a short about Oersted discovering electromagnetism in 1820."},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "spec", "strict": True, "schema": SPEC_SCHEMA},
            },
            "max_tokens": 400,
            "temperature": 0.7,
        }, args.timeout)
        dt = time.time() - t0
        content = r["choices"][0]["message"]["content"]
        spec = json.loads(content)
        assert isinstance(spec["beats"], list) and len(spec["beats"]) == 3
        assert spec["topic"] and spec["hook"]
        usage = r.get("usage", {})
        tps = usage.get("completion_tokens", 0) / dt if dt > 0 else 0
        print(f"[ok] schema-constrained JSON parsed ({dt:.1f}s, ~{tps:.0f} tok/s) hook={spec['hook']!r}")
    except Exception as e:  # noqa: BLE001 - smoke test reports anything
        failures.append(f"json_schema: {e}")
        print(f"[FAIL] schema-constrained JSON: {e}")

    # 3. tool-calling
    t0 = time.time()
    try:
        r = post(base, "/v1/chat/completions", {
            "model": model_id,
            "messages": [
                {"role": "user", "content": "Resolve the source with DOI 10.1002/andp.18200650402 before citing it."},
            ],
            "tools": [WEATHER_TOOL],
            "max_tokens": 200,
            "temperature": 0.1,
        }, args.timeout)
        dt = time.time() - t0
        msg = r["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        assert calls, f"no tool_calls emitted; content was: {msg.get('content')!r}"
        fn = calls[0]["function"]
        assert fn["name"] == "lookup_source"
        args_obj = json.loads(fn["arguments"])
        assert "10.1002" in args_obj.get("doi", "")
        print(f"[ok] tool call emitted correctly ({dt:.1f}s): {fn['name']}({args_obj})")
    except Exception as e:  # noqa: BLE001
        failures.append(f"tool_call: {e}")
        print(f"[FAIL] tool-calling: {e}")

    if failures:
        print(f"\nRESULT: {len(failures)} failure(s)")
        return 1
    print("\nRESULT: all smoke tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
