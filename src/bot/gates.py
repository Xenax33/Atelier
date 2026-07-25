"""Discord gate UI: restart-proof buttons that resume the LangGraph pipeline.

Every gate button is a DynamicItem whose custom_id encodes (run_id, stage, action):
    atelier:g:<run_id>:<stage>:<action>
DynamicItems are matched by REGEX at interaction time, so a button posted before a bot
restart still works after relaunch: the checkpoint holds the graph state, the custom_id
holds the routing. This is the whole HITL durability story (ADR-0003 + TASK-004 proof).
"""

from __future__ import annotations

import re

import discord
from discord import ui

_TEMPLATE = r"atelier:g:(?P<rid>[\w\-]+):(?P<stage>script|audio|final):(?P<action>approve|regen|reject)"

_LABELS = {
    "approve": ("Approve", discord.ButtonStyle.success),
    "regen": ("Regenerate", discord.ButtonStyle.primary),
    "reject": ("Reject", discord.ButtonStyle.danger),
}


class GateAction(ui.DynamicItem[ui.Button], template=_TEMPLATE):
    def __init__(self, rid: str, stage: str, action: str) -> None:
        label, style = _LABELS[action]
        super().__init__(
            ui.Button(label=label, style=style, custom_id=f"atelier:g:{rid}:{stage}:{action}")
        )
        self.rid, self.stage, self.action = rid, stage, action

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: ui.Button,
                             match: re.Match[str]) -> GateAction:
        return cls(match["rid"], match["stage"], match["action"])

    async def callback(self, interaction: discord.Interaction) -> None:
        runner = getattr(interaction.client, "pipeline", None)
        if runner is None:
            await interaction.response.send_message("pipeline runner not ready", ephemeral=True)
            return
        if self.action == "regen":
            await interaction.response.send_modal(FeedbackModal(self.rid, self.stage))
            return
        await interaction.response.defer(thinking=True)
        await interaction.followup.send(
            f"`{self.rid}`: {self.action} at {self.stage} gate. Working...", ephemeral=False
        )
        await runner.resume(self.rid, {"action": self.action})


class FeedbackModal(ui.Modal):
    feedback = ui.TextInput(
        label="What should change?",
        style=discord.TextStyle.paragraph,
        placeholder="e.g. punchier hook, more concrete dates, aim for 140 spoken words",
        required=False,
        max_length=1000,
    )

    def __init__(self, rid: str, stage: str) -> None:
        super().__init__(title=f"Regenerate ({stage})")
        self.rid, self.stage = rid, stage

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"`{self.rid}`: regenerating with your feedback...", ephemeral=False
        )
        runner = interaction.client.pipeline
        await runner.resume(self.rid, {"action": "regen", "feedback": str(self.feedback.value or "")})


def gate_view(rid: str, stage: str) -> ui.View:
    view = ui.View(timeout=None)
    view.add_item(GateAction(rid, stage, "approve"))
    view.add_item(GateAction(rid, stage, "regen"))
    if stage in ("script", "final"):
        view.add_item(GateAction(rid, stage, "reject"))
    return view
