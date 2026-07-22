"""Atelier/1 - local open-source science-Shorts studio.

A seamed modular monolith. See CONTEXT.md and docs/ARCHITECTURE.md.

The three load-bearing seams (do not break):
  - gateway/  : OpenAI-compatible model gateway (agents never import an inference engine)
  - store/    : checkpointer + dedup interface (SqliteSaver -> PostgresSaver)
  - tools/    : pure typed functions (wrap as MCP/queue-RPC later)
"""
