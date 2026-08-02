"""agents/ - the LLM-reasoning agents (one module each).

Implemented: researcher (ideation + evidence gathering + query distillation), scriptwriter
(3 angle-varied candidates), editor (ranking + critiques), factcheck (claim audit).
Planned: visual director as its own agent (style prompts currently come from the scriptwriter).
All reason via the gateway/ (OpenAI-compatible) - never import an inference engine directly.
Structured outputs use JSON-schema constrained decoding.

The Fact-Checker is mandatory and non-skippable: LLM entailment against the evidence pack plus
mechanical citation-URL resolution (supported verdicts are downgraded if the source does not
resolve). Crossref title-matching is tracked in TASK-021. See ARCHITECTURE §5 and Risk R4.
"""
