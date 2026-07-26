"""Fact-checker agent: audit every factual claim in a drafted spec against the evidence pack.

Mandatory, non-skippable (ARCHITECTURE section 5 / Risk R4: local models fabricate facts).
v1 scope: LLM entailment against gathered evidence, verdicts surfaced at Gate 1.
Next iteration: mechanical DOI/citation resolution (HTTP 200 + Crossref title match).
"""

from __future__ import annotations

from ..gateway.client import chat_json
from ..graph.state import ShortSpec
from .researcher import evidence_digest

CLAIMS_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "minItems": 1,
            "maxItems": 15,
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["supported", "uncertain", "unsupported"]},
                    "evidence_ref": {"type": "string"},
                },
                "required": ["claim", "verdict", "evidence_ref"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["claims"],
    "additionalProperties": False,
}

_SYSTEM = """You are a strict fact-checker for a science-history channel. One wrong fact kills
the channel's credibility, so be conservative.

From the script, extract every distinct FACTUAL claim (names, dates, places, causal assertions,
firsts/records). For each, compare against the evidence pack ONLY:
- supported: the evidence pack directly backs it.
- uncertain: plausible but the pack does not confirm it (or details differ slightly).
- unsupported: the pack contradicts it, or it is a specific checkable assertion with zero backing.
evidence_ref: the [index] of the supporting evidence item, or "none".
Do not use your own knowledge to mark something supported; the pack is the ground truth here."""


def audit_spec(spec: ShortSpec, evidence: list[dict]) -> list[dict]:
    script = " ".join(
        [spec["hook"]] + [b["narration"] for b in spec["beats"]] + [spec["payoff"]]
    )
    result = chat_json(
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"EVIDENCE PACK:\n{evidence_digest(evidence)}\n\nSCRIPT:\n{script}"},
        ],
        schema=CLAIMS_SCHEMA, schema_name="claims", temperature=0.1, max_tokens=1600,
    )
    return result["claims"]
