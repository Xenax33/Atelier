"""store/ - persistence: checkpointer + dedup/vector interface (SEAM #2).

Responsibility: wrap LangGraph's checkpointer (SqliteSaver now -> PostgresSaver at v1+) behind a stable
interface, plus the embedding/dedup store (sqlite-vec -> pgvector) that powers topic dedup and the
production/episodic memory.

Note: the EDITORIAL TASTE MODEL (what the user likes) is a separate concern living in prompts/editorial-profile.md,
NOT in this vector store - do not conflate "what we made" with "what the user prefers". See docs/adr/0010.
"""
