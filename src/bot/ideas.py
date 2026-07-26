"""The /ideas flow: researcher proposes pitched topics, user picks one with a button.

Idea batches persist to state/ideas/<batch_id>.json, and pick buttons are DynamicItems
(custom_id atelier:i:<batch>:<idx>), so an ideas card keeps working after bot restarts.
Picking an idea starts the normal pipeline exactly as /new-short would.
"""

from __future__ import annotations

import json
import pathlib
import re
import time
import uuid

import discord
from discord import ui

IDEAS_DIR = pathlib.Path("state/ideas")
_TEMPLATE = r"atelier:i:(?P<batch>[\w\-]+):(?P<idx>\d+)"


def save_batch(ideas: list[dict]) -> str:
    batch = f"{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    IDEAS_DIR.mkdir(parents=True, exist_ok=True)
    (IDEAS_DIR / f"{batch}.json").write_text(json.dumps(ideas, indent=1), encoding="utf-8")
    return batch


def load_batch(batch: str) -> list[dict] | None:
    p = IDEAS_DIR / f"{batch}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


class IdeaPick(ui.DynamicItem[ui.Button], template=_TEMPLATE):
    def __init__(self, batch: str, idx: int) -> None:
        super().__init__(
            ui.Button(label=f"Pick {idx + 1}", style=discord.ButtonStyle.primary,
                      custom_id=f"atelier:i:{batch}:{idx}")
        )
        self.batch, self.idx = batch, idx

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: ui.Button,
                             match: re.Match[str]) -> IdeaPick:
        return cls(match["batch"], int(match["idx"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        ideas = load_batch(self.batch)
        if not ideas or self.idx >= len(ideas):
            await interaction.response.send_message("that ideas batch is gone", ephemeral=True)
            return
        idea = ideas[self.idx]
        await interaction.response.send_message(
            f"Picked: **{idea['topic']}**\nDrafting the script..."
        )
        import asyncio

        asyncio.create_task(interaction.client.pipeline.start(idea["topic"]))


def ideas_embed(ideas: list[dict], batch: str) -> discord.Embed:
    e = discord.Embed(
        title="Topic ideas - pick one",
        description="Researched from today-in-history + live leads. Or use /new-short for your own.",
        colour=discord.Colour.gold(),
    )
    for i, idea in enumerate(ideas):
        e.add_field(
            name=f"{i + 1}. {idea['topic'][:250]}",
            value=(idea["pitch"] + "\n*Hook: " + idea["hook_angle"] + "*")[:1024],
            inline=False,
        )
    e.set_footer(text=f"batch {batch}")
    return e


def ideas_view(batch: str, count: int) -> ui.View:
    view = ui.View(timeout=None)
    for i in range(min(count, 8)):
        view.add_item(IdeaPick(batch, i))
    return view
