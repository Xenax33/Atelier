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

    # Wikidata year cross-check (R&D 4.5, TASK-034): deterministic, ADVISORY-only flags
    # for near-miss dates (the classic off-by-one). Emitted as "uncertain" claims so the
    # existing flagged-claims card at Gate 1 renders them with zero bot changes. Terms are
    # entities already identified upstream - no fragile name extraction from prose.
    try:
        from ..tools.research import wikidata_year_flags

        terms = [e["title"] for e in evidence if e.get("source") == "wikipedia"]
        terms += [s for b in state["spec"]["beats"]
                  if (s := (b.get("archival_subject") or "").strip())]
        for flag in wikidata_year_flags(terms, state.get("narration_text", "")):
            claims.append({"claim": flag, "verdict": "uncertain", "evidence_ref": "none",
                           "citation_ok": False, "citation_url": ""})
    except Exception:  # noqa: BLE001 - advisory layer must never block the audit
        pass
    run = _run_dir(state)
    (run / "claims.json").write_text(json.dumps(claims, indent=1), encoding="utf-8")

    # Archival plan preview for Gate 1 (search only, no CLIP/downloads - keeps the gate fast):
    # which beats want real images and what the archives hold for them.
    plan: list[dict] = []
    try:
        from ..tools.archival import find_archival

        for i, b in enumerate(state["spec"]["beats"]):
            subject = (b.get("archival_subject") or "").strip()
            if not subject:
                continue
            cands = find_archival(subject)
            plan.append({
                "beat": i, "subject": subject, "candidates": len(cands),
                "top_title": cands[0].title if cands else "",
                "top_url": cands[0].source_url if cands else "",
            })
    except Exception:  # noqa: BLE001 - preview is informational only
        pass
    return {"claims": claims, "archival_plan": plan}


def gate_script(state: ShortState) -> Command[Literal["draft", "factcheck", "tts", "abort"]]:
    decision = interrupt({"stage": "script", "spec": state["spec"],
                          "candidates": state.get("candidates", []),
                          "critiques": state.get("critiques", []),
                          "audited_index": state.get("audited_index", 0),
                          "claims": state.get("claims", []),
                          "archival_plan": state.get("archival_plan", []),
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
    """Per-segment synthesis (hook / beats / outro) with explicit gaps: exact beat
    timestamps land in assets/beat_timing.json for assemble's beat-synced cuts, and
    the wav ships through the ffmpeg voice chain (R&D 2026-08-03, 5.2/5.3)."""
    from ..workers.tts import render_narration_segments, spec_segments

    run = _run_dir(state)
    audio = run / "assets" / "narration.wav"
    seconds, _timing = render_narration_segments(spec_segments(state["spec"]), audio)
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
    Archival failures still fall back to SDXL - archival is an enhancement, never a
    blocker - but every decision AND every swallowed error is now recorded in
    assets/visual_plan.json (2026-08-06: an off-topic-image + zero-archival run was
    undiagnosable because this node's two `except: pass` blocks left no trace)."""
    import json

    from ..tools.archival import (
        ARCHIVAL_MIN_SCORE,
        fetch_and_frame,
        find_archival,
        score_candidates,
    )
    from ..workers.visuals import render_beat_stills

    run = _run_dir(state)
    assets = run / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    beats = [dict(b) for b in state["spec"]["beats"]]
    # Writer prompts snapshotted BEFORE the Visual Director overwrites them: archival CLIP
    # scoring must compare candidates against the writer's LITERAL scene description. Scoring
    # against the Director's metaphor was a live bug (2026-08-06): a genuine portrait scores
    # near-zero against "a marble rolling down a spiral funnel", lands under the 0.28
    # threshold, and every archival beat silently falls back to SDXL.
    writer_prompts = [(b.get("visual_prompt") or "").strip() for b in beats]
    plan: list[dict] = [{"beat": i, "narration": b.get("narration", ""),
                         "prompt": writer_prompts[i], "prompt_source": "writer",
                         "style": "painterly", "archival": {"status": "not-requested"}}
                        for i, b in enumerate(beats)]

    # Visual Director pass: narration -> depictable scene (literal-first, anchored metaphor
    # as fallback - agents/visdir.py). On failure the writer prompts still render.
    styles = ["painterly"] * len(beats)  # safe default (people assumed)
    try:
        from ..agents.visdir import direct_visuals

        directed, has_people = direct_visuals(beats, state.get("topic", ""))
        for j, (b, p) in enumerate(zip(beats, directed, strict=True)):
            if p.strip():
                b["visual_prompt"] = p.strip()
                plan[j]["prompt"] = p.strip()
                plan[j]["prompt_source"] = "director"
            # Smart routing (2026-08-02): cinematic realism only for people-free scenes.
            styles[j] = "painterly" if has_people[j] else "cinematic"
            plan[j]["style"] = styles[j]
    except Exception as e:  # noqa: BLE001 - director is an enhancer; record why it was skipped
        for entry in plan:
            entry["director_error"] = repr(e)
    paths: list[str | None] = [None] * len(beats)
    used: list[dict] = []
    # Resume-friendly: a beat still that already exists in THIS run's assets was rendered
    # by an earlier attempt of this same run (same spec, same seeds) - reuse it instead of
    # burning ~5 GPU-minutes again (2026-08-04: a crash on beat 5 of 5 cost a full re-render).
    # Only for non-archival beats: archival ones must refetch so the license/credit metadata
    # in archival_used stays complete.
    for i, b in enumerate(beats):
        if not (b.get("archival_subject") or "").strip():
            existing = assets / f"beat_{i:02d}.png"
            if existing.exists():
                paths[i] = str(existing)
                plan[i]["reused"] = True
    for i, b in enumerate(beats):
        if paths[i] is not None:
            continue
        subject = (b.get("archival_subject") or "").strip()
        if not subject:
            continue
        try:
            scored = score_candidates(find_archival(subject), subject, writer_prompts[i])
            if scored and scored[0][0] >= ARCHIVAL_MIN_SCORE:
                best = scored[0][1]
                paths[i] = fetch_and_frame(best, str(assets / f"beat_{i:02d}.png"))
                used.append({"beat": i, "score": scored[0][0], **best.to_dict()})
                plan[i]["archival"] = {"status": "used", "subject": subject,
                                       "score": scored[0][0], "source": best.source_url}
            else:
                plan[i]["archival"] = {
                    "status": "below-threshold" if scored else "no-candidates",
                    "subject": subject, "candidates": len(scored),
                    "top_score": scored[0][0] if scored else None,
                    "threshold": ARCHIVAL_MIN_SCORE,
                }
        except Exception as e:  # noqa: BLE001 - fall through to SDXL, but leave the reason
            plan[i]["archival"] = {"status": "error", "subject": subject, "error": repr(e)}

    todo = [i for i in range(len(beats)) if paths[i] is None]
    prompts_to_render = []
    for i in todo:
        p = (beats[i].get("visual_prompt") or "").strip()
        if not p:
            # Style-vacuum guard: an empty prompt + style suffix makes SDXL invent an
            # arbitrary subject (the off-topic-image failure class). Anchor to the topic.
            p = f"{state.get('topic', '')}, {beats[i].get('caption', '')}".strip(", ")
            plan[i]["prompt"] = p
            plan[i]["prompt_source"] = "topic-fallback"
        prompts_to_render.append(p)
    # Snapshot the plan BEFORE the GPU dance so a mid-render crash still leaves the
    # full per-beat decision trail on disk for /resume-time diagnosis.
    plan_file = assets / "visual_plan.json"
    plan_file.write_text(json.dumps(plan, indent=1), encoding="utf-8")
    if todo:
        rendered = render_beat_stills(
            prompts_to_render, assets, REPO_ROOT, indices=todo,
            styles=[styles[i] for i in todo])
        for i, p in zip(todo, rendered, strict=True):
            paths[i] = p
    for i, p in enumerate(paths):
        plan[i]["image"] = p
    plan_file.write_text(json.dumps(plan, indent=1), encoding="utf-8")
    return {"image_paths": [p for p in paths if p], "archival_used": used}


def captions(state: ShortState) -> dict:
    """ASR for TIMING, script for TEXT (R&D 7.3): raw whisper words land in
    words_asr.json (kept for mispronunciation diffing later); words.json - what the
    caption burner consumes - carries the script's own spelling on ASR timings."""
    import json

    from ..workers.captions import align_to_script, word_timestamps

    run = _run_dir(state)
    out = run / "assets" / "words.json"
    asr = word_timestamps(state["audio_path"], run / "assets" / "words_asr.json")
    try:
        words = align_to_script(state.get("narration_text", ""), asr)
    except Exception:  # noqa: BLE001 - alignment is an enhancer; ASR captions still work
        words = asr
    out.write_text(json.dumps(words, indent=1), encoding="utf-8")
    return {"words_path": str(out)}


def assemble_node(state: ShortState) -> dict:
    from ..workers.assemble import assemble

    run = _run_dir(state)
    master, proxy = assemble(
        state["spec"], state["audio_path"], state["image_paths"], state["words_path"],
        str(run / "render" / "master.mp4"), str(run / "render" / "proxy.mp4"),
        music_dir=str(REPO_ROOT / "assets" / "music"), music_seed=state["run_id"],
        archival_beats=[u["beat"] for u in state.get("archival_used", [])],
    )
    return {"master_path": master, "proxy_path": proxy}


def gate_final(state: ShortState) -> Command[Literal["deliver", "abort"]]:
    decision = interrupt({"stage": "final", "master_path": state["master_path"],
                          "proxy_path": state["proxy_path"],
                          "archival_used": state.get("archival_used", [])})
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

    def _clean(s: str) -> str:
        """Published metadata gets plain ASCII punctuation (owner preference: the em-dash
        habit of LLMs reads as AI-generated)."""
        return (s.replace("—", " - ").replace("–", "-").replace("…", "...")
                 .replace("‘", "'").replace("’", "'")
                 .replace("“", '"').replace("”", '"').replace("  ", " "))

    title, description = _clean(spec["title"]), _clean(spec["description"])
    tags = " ".join("#" + t.lstrip("#") for t in spec["hashtags"])
    credits = ""
    if state.get("archival_used"):
        lines = "\n".join("- " + u["attribution"] for u in state["archival_used"])
        credits = f"\n\n## Image credits (paste into the YouTube description)\n{lines}\n"
    meta.write_text(
        f"# {title}\n\n{description}\n\n{tags}\n{credits}\n"
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
