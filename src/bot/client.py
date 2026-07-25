"""The Atelier Discord bot (control plane).

Design rules (see src/bot/__init__.py and docs/ARCHITECTURE.md):
  - Minimal Gateway Intents: guilds only. No Message Content, no Members, no Presence.
  - Slash commands are synced to the single configured guild (instant, no 1-hour global wait).
  - Persistent views are re-registered in setup_hook so buttons survive restarts.
  - Heavy work never runs on the event loop (nothing heavy exists yet; keep it that way).
"""

from __future__ import annotations

import logging
import time

import discord
import httpx
from discord.ext import commands

from ..config import Settings
from .views import ControlPanel

log = logging.getLogger("atelier.bot")


class AtelierBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.settings = settings
        self._announced = False

    async def setup_hook(self) -> None:
        # Re-register persistent views BEFORE any interaction can arrive, so buttons on
        # messages from previous runs keep working (TASK-004's definition of done).
        self.add_view(ControlPanel(self.settings.model_gateway_base_url))
        guild = discord.Object(id=self.settings.discord_guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        log.info("slash commands synced to guild %s", self.settings.discord_guild_id)

    async def on_ready(self) -> None:
        log.info("logged in as %s (id=%s)", self.user, self.user.id if self.user else "?")
        if self._announced:
            return
        self._announced = True
        channel = self.get_channel(self.settings.discord_control_channel_id)
        if channel is None:
            try:
                channel = await self.fetch_channel(self.settings.discord_control_channel_id)
            except discord.HTTPException:
                log.error(
                    "control channel %s not found; check DISCORD_CONTROL_CHANNEL_ID "
                    "and that the bot was invited to the server",
                    self.settings.discord_control_channel_id,
                )
                return
        embed = discord.Embed(
            title="Atelier stack is up",
            description=(
                "Control panel for the local studio. Buttons below stay clickable across "
                "bot restarts (persistent views)."
            ),
            colour=discord.Colour.green(),
        )
        embed.add_field(name="Brain", value="Qwen3-4B-Instruct-2507 via llama.cpp Vulkan", inline=False)
        embed.add_field(name="Commands", value="/status, or use the buttons", inline=False)
        await channel.send(embed=embed, view=ControlPanel(self.settings.model_gateway_base_url))


def build_bot(settings: Settings) -> AtelierBot:
    bot = AtelierBot(settings)

    @bot.tree.command(description="Health of the local AI stack")
    async def status(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        base = settings.model_gateway_base_url
        health_url = base.removesuffix("/v1") + "/health"
        lines = []
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(health_url)
            dt = (time.monotonic() - t0) * 1000
            lines.append(f"{'🟢' if r.status_code == 200 else '🔴'} brain (llama gateway): HTTP {r.status_code}, {dt:.0f} ms")
        except httpx.HTTPError as e:
            lines.append(f"🔴 brain (llama gateway): unreachable ({type(e).__name__})")
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(settings.comfyui_base_url)
            lines.append(f"🟢 visuals (ComfyUI): HTTP {r.status_code}")
        except httpx.HTTPError:
            lines.append("⚪ visuals (ComfyUI): not running (TASK-002 pending)")
        lines.append(f"🟢 bot: websocket {interaction.client.latency * 1000:.0f} ms")
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    return bot
