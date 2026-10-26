"""Frozen, condition-blind prompt material for the independent label panel."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

PROMPT_VERSION = "track22-collusion-label-v3"
PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
RUBRIC = (PROMPT_DIR / "label_judge_rubric.txt").read_text(encoding="utf-8").rstrip("\n")
SYSTEM_PROMPT = (PROMPT_DIR / "label_judge_system.txt").read_text(encoding="utf-8").rstrip("\n")

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "agreement_detected": {"type": "boolean"},
        "rule_violation_detected": {"type": "boolean"},
        "agreement_executed": {"type": "boolean"},
        "label": {"type": ["integer", "null"], "enum": [0, 1, None]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "contradictory_evidence": {"type": "boolean"},
        "evidence": {"type": "array", "items": {"type": "object", "properties": {
            "event_id": {"type": "string"}, "quote": {"type": "string"}, "reason": {"type": "string"}
        }, "required": ["event_id", "quote", "reason"], "additionalProperties": False}},
        "uncertainty": {"type": "string"}
    },
    "required": ["agreement_detected", "rule_violation_detected", "agreement_executed", "label", "confidence", "contradictory_evidence", "evidence", "uncertainty"],
    "additionalProperties": False
}

def make_prompt(case: dict) -> str:
    # The packet builder has already removed condition identifiers, private metadata,
    # judge outputs, and labels. It may include private agent plans as authorized evidence.
    return json.dumps({"rubric": RUBRIC, "case": case}, sort_keys=True, ensure_ascii=False)

def prompt_sha256() -> str:
    body = json.dumps({"version": PROMPT_VERSION, "system": SYSTEM_PROMPT,
                       "rubric": RUBRIC, "schema": OUTPUT_SCHEMA}, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()
