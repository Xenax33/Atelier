"""Persistent Discord views (the control-surface buttons).

Persistence rules (this is what TASK-004 proves):
  - View(timeout=None) and a FIXED custom_id on every interactive item.
  - The bot re-registers these views in setup_hook() on every boot, so buttons on
    messages posted before a restart keep working after it.
"""

from __future__ import annotations

import time

import discord
import httpx
from discord import ui

GATEWAY_HEALTH_TIMEOUT = 5.0


class ControlPanel(ui.View):
    """The standing control panel posted to #control on boot."""

    def __init__(self, gateway_base_url: str) -> None:
        super().__init__(timeout=None)
        # Note: base_url is captured at construction; the re-registered view after a
        # restart gets the current .env value, which is what we want.
        self._health_url = gateway_base_url.removesuffix("/v1") + "/health"
        self._models_url = gateway_base_url.rstrip("/") + "/models"

    @ui.button(label="Ping bot", style=discord.ButtonStyle.primary, custom_id="atelier:ping")
    async def ping(self, interaction: discord.Interaction, button: ui.Button) -> None:
        latency_ms = interaction.client.latency * 1000
        await interaction.response.send_message(
            f"pong. Gateway websocket latency: {latency_ms:.0f} ms. "
            "If this message arrived after a bot restart, persistent views work.",
            ephemeral=True,
        )

    @ui.button(label="Check brain", style=discord.ButtonStyle.secondary, custom_id="atelier:brain")
    async def brain(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=GATEWAY_HEALTH_TIMEOUT) as client:
                health = await client.get(self._health_url)
                models = await client.get(self._models_url)
            dt_ms = (time.monotonic() - t0) * 1000
            model_id = "?"
            if models.status_code == 200:
                data = models.json().get("data", [])
                if data:
                    model_id = data[0].get("id", "?").rsplit("\\", 1)[-1]
            ok = health.status_code == 200
            msg = (
                f"{'🟢' if ok else '🔴'} llama gateway: HTTP {health.status_code} in {dt_ms:.0f} ms\n"
                f"model: `{model_id}`"
            )
        except httpx.HTTPError as e:
            msg = f"🔴 llama gateway unreachable: `{type(e).__name__}` (is start-day.ps1 running?)"
        await interaction.followup.send(msg, ephemeral=True)
