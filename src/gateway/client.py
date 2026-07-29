"""Thin client for the model gateway (SEAM #1).

All LLM calls in the codebase go through here. Synchronous by design: pipeline nodes
run in a worker thread (the bot calls graph.invoke via asyncio.to_thread), so blocking
HTTP is fine and keeps the workers simple.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from ..config import get_settings

_TIMEOUT = httpx.Timeout(300.0, connect=10.0)


def gateway_healthy() -> bool:
    s = get_settings()
    base = s.model_gateway_base_url.removesuffix("/v1")
    try:
        return httpx.get(base + "/health", timeout=5.0).status_code == 200
    except httpx.HTTPError:
        return False


def _ensure_brain() -> None:
    """Self-healing: if the gateway is down, start llama-server and wait for health.
    (Reaches into workers.visuals for the canonical launch; supervision via nssm is the
    long-term answer, this kills the 'brain was down' failure class meanwhile.)"""
    import pathlib

    from ..workers.visuals import start_llama

    start_llama(pathlib.Path(__file__).resolve().parents[2])


def chat_json(
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    schema_name: str = "output",
    temperature: float = 0.7,
    max_tokens: int = 1600,
) -> dict[str, Any]:
    """Schema-constrained chat completion. Returns the parsed JSON object.

    Constrained decoding guarantees SHAPE, not semantics: enforce word/length limits
    in prompts and validate content in the caller (ADR-0011 lesson).
    """
    s = get_settings()
    body = {
        "model": s.primary_model,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        },
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    url = s.model_gateway_base_url.rstrip("/") + "/chat/completions"
    try:
        r = httpx.post(url, json=body, timeout=_TIMEOUT)
    except httpx.ConnectError:
        _ensure_brain()
        r = httpx.post(url, json=body, timeout=_TIMEOUT)
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])
