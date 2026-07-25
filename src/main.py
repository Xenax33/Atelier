"""Entrypoint for the Atelier app process (Discord control plane, later + LangGraph).

Launched by start-day.ps1 after the GPU servers are health-gated, or directly:
    .venv\\Scripts\\python -m src.main
Requires a filled .env (copy .env.example). See docs/RUNBOOK.md.
"""

from __future__ import annotations

import logging
import sys

from .bot.client import build_bot
from .config import get_settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    try:
        settings = get_settings()
    except Exception as e:  # pydantic ValidationError, missing .env values
        print(f"Config error: {e}\nCopy .env.example to .env and fill in the Discord values.", file=sys.stderr)
        raise SystemExit(2) from e
    bot = build_bot(settings)
    bot.run(settings.discord_bot_token, log_handler=None)


if __name__ == "__main__":
    main()
