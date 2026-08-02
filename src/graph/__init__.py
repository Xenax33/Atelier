"""graph/ - the LangGraph StateGraph: nodes, edges, shared state schema.

Actual flow (see build.py): research (evidence pack) -> draft (3 candidates) -> edit (rank)
-> factcheck (audit + citation resolution) -> [GATE 1 pick/regen] -> tts -> [GATE 2]
-> visuals -> captions -> assemble -> [GATE 3] -> deliver (metadata for manual upload).
Gates are durable `interrupt()`s; switching candidates at Gate 1 re-audits before proceeding.

Seam: state persists via the store/ checkpointer interface (SqliteSaver now). One `thread_id` per short.
Agents coordinate through the shared state object - no message bus on day one.
"""
