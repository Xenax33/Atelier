"""Bridges Discord and the LangGraph pipeline.

The graph is synchronous and slow (renders take many minutes), so every graph call runs
in a worker thread via asyncio.to_thread; the bot's event loop stays responsive (Risk R10).
One advance at a time per run (a lock per run_id) so double-clicks can't race the graph.
"""

from __future__ import annotations

import asyncio
import logging
import pathlib
import time
import uuid

import discord
from langgraph.types import Command

from ..graph.build import get_graph
from .gates import gate_view

log = logging.getLogger("atelier.pipeline")

MAX_ATTACH_MB = 9.5


class PipelineRunner:
    def __init__(self, bot: discord.Client, control_channel_id: int) -> None:
        self.bot = bot
        self.control_channel_id = control_channel_id
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, rid: str) -> asyncio.Lock:
        return self._locks.setdefault(rid, asyncio.Lock())

    async def _channel(self) -> discord.abc.Messageable:
        ch = self.bot.get_channel(self.control_channel_id)
        return ch or await self.bot.fetch_channel(self.control_channel_id)

    async def start(self, topic: str) -> str:
        rid = f"{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
        cfg = {"configurable": {"thread_id": rid}}
        await self._advance(rid, {"run_id": rid, "topic": topic}, cfg)
        return rid

    async def resume(self, rid: str, payload: dict) -> None:
        cfg = {"configurable": {"thread_id": rid}}
        await self._advance(rid, Command(resume=payload), cfg)

    async def _advance(self, rid: str, graph_input, cfg: dict) -> None:
        async with self._lock(rid):
            graph = get_graph()
            try:
                result = await asyncio.to_thread(graph.invoke, graph_input, cfg)
            except Exception as e:  # noqa: BLE001 - surfaced to the user, run stays resumable
                log.exception("run %s failed", rid)
                ch = await self._channel()
                await ch.send(f"`{rid}`: pipeline error: `{str(e)[:300]}` (run is still resumable)")
                return
        await self._present(rid, result)

    async def _present(self, rid: str, result: dict) -> None:
        ch = await self._channel()
        intr = result.get("__interrupt__")
        if intr:
            payload = intr[0].value
            stage = payload.get("stage")
            if stage == "script":
                await ch.send(embed=self._script_embed(rid, payload), view=gate_view(rid, "script"))
            elif stage == "audio":
                secs = payload.get("seconds", 0)
                # mp3 preview: Discord's inline player handles mp3 reliably, raw wav not.
                from ..workers.tts import wav_to_mp3

                preview = await asyncio.to_thread(wav_to_mp3, payload["audio_path"])
                await ch.send(
                    content=f"**Gate 2 - narration** `{rid}` ({secs:.0f}s). Listen, then decide:",
                    file=discord.File(preview),
                    view=gate_view(rid, "audio"),
                )
            elif stage == "final":
                files = []
                proxy = pathlib.Path(payload["proxy_path"])
                if proxy.exists() and proxy.stat().st_size < MAX_ATTACH_MB * 1024 * 1024:
                    files = [discord.File(str(proxy))]
                await ch.send(
                    content=(f"**Gate 3 - final review** `{rid}`\nmaster: `{payload['master_path']}`"),
                    files=files,
                    view=gate_view(rid, "final"),
                )
            return
        # No interrupt: the run ended.
        if result.get("error"):
            await ch.send(f"`{rid}`: run ended: {result['error']}")
            return
        meta = result.get("metadata_path")
        text = pathlib.Path(meta).read_text(encoding="utf-8") if meta else ""
        await ch.send(
            f"**`{rid}` DONE.** Upload manually when ready (remember the AI-disclosure tick).\n"
            f"master: `{result.get('master_path')}`\n\n{text[:1500]}"
        )

    @staticmethod
    def _script_embed(rid: str, payload: dict) -> discord.Embed:
        spec = payload["spec"]
        words = len(" ".join([spec["hook"]] + [b["narration"] for b in spec["beats"]]
                             + [spec["payoff"], spec["cta"]]).split())
        e = discord.Embed(
            title=f"Gate 1 - script (attempt {payload.get('attempt', 1)})",
            description=f"**{spec['title']}**\n\n**Hook:** {spec['hook']}",
            colour=discord.Colour.blurple(),
        )
        for i, b in enumerate(spec["beats"]):
            e.add_field(name=f"Beat {i + 1} - {b['caption']}", value=b["narration"][:1024], inline=False)
        e.add_field(name="Payoff", value=spec["payoff"], inline=False)
        e.add_field(name="CTA", value=spec["cta"], inline=False)
        claims = payload.get("claims", [])
        flagged = [c for c in claims if c.get("verdict") != "supported"]
        if claims:
            if flagged:
                lines = "\n".join(
                    f"{'🔴' if c['verdict'] == 'unsupported' else '🟡'} {c['claim'][:150]}"
                    for c in flagged[:6]
                )
                e.add_field(name=f"⚠ Fact-check: {len(flagged)}/{len(claims)} claims need your eye",
                            value=lines[:1024], inline=False)
            else:
                e.add_field(name="Fact-check", value=f"🟢 all {len(claims)} claims supported by evidence",
                            inline=False)
        e.set_footer(text=f"{rid} | {words} spoken words (target 130-155)")
        return e
