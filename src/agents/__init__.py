"""agents/ - the LLM-reasoning agents (one module each).

Roster: researcher, factcheck, scriptwriter, editor, visdir (visual director), publisher_assistant.
All reason via the gateway/ (OpenAI-compatible) - never import an inference engine directly.
Structured outputs use GBNF/JSON-schema constrained decoding.

The Fact-Checker is mandatory and non-skippable: it mechanically resolves every citation
(HTTP 200 + Crossref/OpenAlex title match). See docs/ARCHITECTURE.md §5 and Risk R4.
"""
