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

from ..agents.scriptwriter import narration_text
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
    from ..agents.scriptwriter import draft_candidates

    ev_text = evidence_digest(state.get("evidence", []))
    candidates = draft_candidates(state["topic"], state.get("script_feedback", ""), ev_text)
    return {
        "candidates": candidates,
        "script_attempts": state.get("script_attempts", 0) + 1,
        "script_feedback": "",
    }


def edit(state: ShortState) -> dict:
    from ..agents.editor import rank_candidates

    ranking = rank_candidates(state["candidates"])
    best = ranking["best"]
    spec = state["candidates"][best]
    return {
        "critiques": ranking["critiques"],
        "audited_index": best,
        "spec": spec,
        "narration_text": narration_text(spec),
    }


def factcheck(state: ShortState) -> dict:
    import json

    from ..agents.factcheck import audit_spec
    from ..tools.research import resolve_url

    evidence = state.get("evidence", [])
    claims = audit_spec(state["spec"], evidence)
    # Mechanical resolution (Risk R4, never trust self-citation): a "supported" verdict only
    # survives if (a) the cited evidence URL resolves right now, and (b) for DOI-backed papers,
    # Crossref's registered title actually matches the evidence title (TASK-021: catches
    # laundered/mistyped DOIs that still return HTTP 200 on doi.org).
    from ..tools.research import crossref_doi_title, title_similarity

    resolved: dict[int, bool] = {}
    for c in claims:
        ref = c.get("evidence_ref", "none")
        if not ref.isdigit() or int(ref) >= len(evidence):
            c["citation_ok"] = False
            continue
        i = int(ref)
        ev = evidence[i]
        if i not in resolved:
            ok = resolve_url(ev.get("url", ""))
            if ok and ev.get("doi"):
                registered = crossref_doi_title(ev["doi"])
                ok = bool(registered) and title_similarity(registered, ev.get("title", "")) >= 0.6
            resolved[i] = ok
        c["citation_ok"] = resolved[i]
        c["citation_url"] = ev.get("url", "")
        if c["verdict"] == "supported" and not c["citation_ok"]:
            c["verdict"] = "uncertain"
    run = _run_dir(state)
    (run / "claims.json").write_text(json.dumps(claims, indent=1), encoding="utf-8")
    return {"claims": claims}


def gate_script(state: ShortState) -> Command[Literal["draft", "factcheck", "tts", "abort"]]:
    decision = interrupt({"stage": "script", "spec": state["spec"],
                          "candidates": state.get("candidates", []),
                          "critiques": state.get("critiques", []),
                          "audited_index": state.get("audited_index", 0),
                          "claims": state.get("claims", []),
                          "attempt": state.get("script_attempts", 1)})
    action = decision.get("action")
    if action == "approve":  # approve = accept the audited/recommended candidate
        return Command(goto="tts")
    if action == "pick":
        i = int(decision.get("index", state.get("audited_index", 0)))
        candidates = state.get("candidates", [state["spec"]])
        i = min(max(i, 0), len(candidates) - 1)
        if i == state.get("audited_index"):
            return Command(goto="tts")
        # A different candidate than the audited one: re-audit it, then re-present the gate
        # so the human sees ITS fact-check flags before committing (the audit must never lag
        # the chosen script).
        chosen = candidates[i]
        return Command(goto="factcheck", update={
            "spec": chosen, "audited_index": i, "narration_text": narration_text(chosen)})
    if action == "regen":
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
    """Per beat: archival image if the writer flagged one AND a license-safe, relevant
    candidate exists (CPU/network work, done BEFORE the GPU dance); SDXL for the rest.
    Archival failures fall back to SDXL silently - archival is an enhancement, never a blocker."""
    from ..tools.archival import (
        ARCHIVAL_MIN_SCORE,
        fetch_and_frame,
        find_archival,
        score_candidates,
    )
    from ..workers.visuals import render_beat_stills

    run = _run_dir(state)
    assets = run / "assets"
    beats = state["spec"]["beats"]
    paths: list[str | None] = [None] * len(beats)
    used: list[dict] = []
    for i, b in enumerate(beats):
        subject = (b.get("archival_subject") or "").strip()
        if not subject:
            continue
        try:
            scored = score_candidates(find_archival(subject), subject, b.get("visual_prompt", ""))
            if scored and scored[0][0] >= ARCHIVAL_MIN_SCORE:
                best = scored[0][1]
                paths[i] = fetch_and_frame(best, str(assets / f"beat_{i:02d}.png"))
                used.append({"beat": i, "score": scored[0][0], **best.to_dict()})
        except Exception:  # noqa: BLE001 - fall through to SDXL
            pass
    todo = [i for i in range(len(beats)) if paths[i] is None]
    if todo:
        rendered = render_beat_stills(
            [beats[i]["visual_prompt"] for i in todo], assets, REPO_ROOT, indices=todo)
        for i, p in zip(todo, rendered, strict=True):
            paths[i] = p
    return {"image_paths": [p for p in paths if p], "archival_used": used}


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
    try:
        from ..store.memory import remember_video

        remember_video(state["run_id"], spec["title"], state.get("topic", ""))
    except Exception:  # noqa: BLE001 - memory failures must never block delivery
        pass
    meta = run / "metadata.md"
    tags = " ".join("#" + t.lstrip("#") for t in spec["hashtags"])
    credits = ""
    if state.get("archival_used"):
        lines = "\n".join("- " + u["attribution"] for u in state["archival_used"])
        credits = f"\n\n## Image credits (paste into the YouTube description)\n{lines}\n"
    meta.write_text(
        f"# {spec['title']}\n\n{spec['description']}\n\n{tags}\n{credits}\n"
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
    g.add_node("edit", edit)
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
    g.add_edge("draft", "edit")
    g.add_edge("edit", "factcheck")
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
