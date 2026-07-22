"""graph/ — the LangGraph StateGraph: nodes, edges, shared state schema.

Responsibility: orchestrates researcher -> dedup -> factcheck -> scriptwriter -> editor -> [GATE 1]
-> tts -> [GATE 2] -> visuals -> assemble -> [GATE 3] -> publish. Gates are durable `interrupt()`s.

Seam: state persists via the store/ checkpointer interface (SqliteSaver now). One `thread_id` per short.
Agents coordinate through the shared state object — no message bus on day one.
"""
