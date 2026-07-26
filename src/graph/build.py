"""The pipeline StateGraph: /new-short -> script -> GATE1 -> voice -> GATE2 -> visuals
-> captions -> assemble -> GATE3 -> deliver. One thread_id per short, checkpointed to
SQLite so any gate can sit open across a PC restart (ADR-0003).

Gates are `interrupt()` calls. Resume payloads (from Discord buttons):
  GATE1 script: {"action": "approve"} | {"action": "regen", "feedback": str} | {"action": "reject"}
  GATE2 audio:  {"action": "approve"} | {"action": "regen"}   (regen returns to script)
  GATE3 final:  {"action": "approve"} | {"action": "reject"}

Nodes are synchronous on purpose: the bot runs graph calls in a worker thread
(asyncio.to_thread), keeping the Discord event loop free during long renders.
"""

from __future__ import annotations

import pathlib
import sqlite3
from typing import Literal

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from ..agents.scriptwriter import draft_spec, narration_text
from ..config import get_settings
from .state import ShortState

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _run_dir(state: ShortState) -> pathlib.Path:
    d = pathlib.Path(get_settings().state_dir) / "runs" / state["run_id"]
    d.mkdir(parents=True, exist_ok=True)
    return d


# --- nodes ---------------------------------------------------------------

def research(state: ShortState) -> dict:
    import json

    from ..agents.researcher import gather_evidence

    evidence = gather_evidence(state["topic"])
    run = _run_dir(state)
    (run / "evidence.json").write_text(json.dumps(evidence, indent=1), encoding="utf-8")
    return {"evidence": evidence}


def draft(state: ShortState) -> dict:
    from ..agents.researcher import evidence_digest

    ev_text = evidence_digest(state.get("evidence", []))
    spec = draft_spec(state["topic"], state.get("script_feedback", ""), ev_text)
    # Word budget is semantics, not schema: enforce with one corrective retry (target 130-155).
    words = len(narration_text(spec).split())
    if words < 120:
        spec = draft_spec(
            state["topic"],
            f"Previous draft was only {words} spoken words; the target is 130-155. "
            "Expand the beats with concrete, evidence-backed detail. "
            + state.get("script_feedback", ""),
            ev_text,
        )
    return {
        "spec": spec,
        "narration_text": narration_text(spec),
        "script_attempts": state.get("script_attempts", 0) + 1,
        "script_feedback": "",
    }


def factcheck(state: ShortState) -> dict:
    import json

    from ..agents.factcheck import audit_spec

    claims = audit_spec(state["spec"], state.get("evidence", []))
    run = _run_dir(state)
    (run / "claims.json").write_text(json.dumps(claims, indent=1), encoding="utf-8")
    return {"claims": claims}


def gate_script(state: ShortState) -> Command[Literal["draft", "tts", "abort"]]:
    decision = interrupt({"stage": "script", "spec": state["spec"],
                          "claims": state.get("claims", []),
                          "attempt": state.get("script_attempts", 1)})
    if decision.get("action") == "approve":
        return Command(goto="tts")
    if decision.get("action") == "regen":
        return Command(goto="draft", update={"script_feedback": decision.get("feedback", "")})
    return Command(goto="abort", update={"error": "rejected at script gate"})


def tts_node(state: ShortState) -> dict:
    from ..workers.tts import render_narration

    run = _run_dir(state)
    audio = run / "assets" / "narration.wav"
    seconds = render_narration(state["narration_text"], audio)
    return {"audio_path": str(audio), "audio_seconds": seconds}


def gate_audio(state: ShortState) -> Command[Literal["visuals", "draft", "abort"]]:
    decision = interrupt({"stage": "audio", "audio_path": state["audio_path"],
                          "seconds": state["audio_seconds"]})
    if decision.get("action") == "approve":
        return Command(goto="visuals")
    if decision.get("action") == "regen":
        return Command(goto="draft", update={"script_feedback": decision.get("feedback", "")})
    return Command(goto="abort", update={"error": "rejected at audio gate"})


def visuals(state: ShortState) -> dict:
    from ..workers.visuals import render_beat_stills

    run = _run_dir(state)
    prompts = [b["visual_prompt"] for b in state["spec"]["beats"]]
    paths = render_beat_stills(prompts, run / "assets", REPO_ROOT)
    return {"image_paths": paths}


def captions(state: ShortState) -> dict:
    from ..workers.captions import word_timestamps

    run = _run_dir(state)
    out = run / "assets" / "words.json"
    word_timestamps(state["audio_path"], out)
    return {"words_path": str(out)}


def assemble_node(state: ShortState) -> dict:
    from ..workers.assemble import assemble

    run = _run_dir(state)
    master, proxy = assemble(
        state["spec"], state["audio_path"], state["image_paths"], state["words_path"],
        str(run / "render" / "master.mp4"), str(run / "render" / "proxy.mp4"),
    )
    return {"master_path": master, "proxy_path": proxy}


def gate_final(state: ShortState) -> Command[Literal["deliver", "abort"]]:
    decision = interrupt({"stage": "final", "master_path": state["master_path"],
                          "proxy_path": state["proxy_path"]})
    if decision.get("action") == "approve":
        return Command(goto="deliver")
    return Command(goto="abort", update={"error": "rejected at final gate"})


def deliver(state: ShortState) -> dict:
    spec = state["spec"]
    run = _run_dir(state)
    meta = run / "metadata.md"
    tags = " ".join("#" + t.lstrip("#") for t in spec["hashtags"])
    meta.write_text(
        f"# {spec['title']}\n\n{spec['description']}\n\n{tags}\n\n"
        f"AI-DISCLOSURE REMINDER: tick 'altered or synthetic content' when uploading.\n"
        f"Master: {state['master_path']}\n",
        encoding="utf-8",
    )
    return {"metadata_path": str(meta)}


def abort(state: ShortState) -> dict:
    return {}


# --- graph ---------------------------------------------------------------

def build_graph(checkpointer) -> object:
    g = StateGraph(ShortState)
    g.add_node("research", research)
    g.add_node("draft", draft)
    g.add_node("factcheck", factcheck)
    g.add_node("gate_script", gate_script)
    g.add_node("tts", tts_node)
    g.add_node("gate_audio", gate_audio)
    g.add_node("visuals", visuals)
    g.add_node("captions", captions)
    g.add_node("assemble", assemble_node)
    g.add_node("gate_final", gate_final)
    g.add_node("deliver", deliver)
    g.add_node("abort", abort)

    g.set_entry_point("research")
    g.add_edge("research", "draft")
    g.add_edge("draft", "factcheck")
    g.add_edge("factcheck", "gate_script")
    g.add_edge("tts", "gate_audio")
    g.add_edge("visuals", "captions")
    g.add_edge("captions", "assemble")
    g.add_edge("assemble", "gate_final")
    g.add_edge("deliver", END)
    g.add_edge("abort", END)
    return g.compile(checkpointer=checkpointer)


_graph = None


def get_graph():
    """Process-wide compiled graph over the SQLite checkpointer (SEAM #2)."""
    global _graph
    if _graph is None:
        conn = sqlite3.connect(get_settings().db_path, check_same_thread=False)
        _graph = build_graph(SqliteSaver(conn))
    return _graph
