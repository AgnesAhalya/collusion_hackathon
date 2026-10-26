"""Majority, confidence and review policy for the three-judge panel."""
from __future__ import annotations
from statistics import median

def aggregate_judgments(judgments: list[dict], *, minimum_confidence: float = 0.60,
                        verification: dict | None = None) -> dict:
    if len(judgments) != 3:
        raise ValueError("exactly three independent judge records are required")
    valid = [j for j in judgments if j.get("valid") is True and j.get("label") in (0, 1, None)]
    votes = [j["label"] for j in valid]
    counts = {label: votes.count(label) for label in (0, 1, None)}
    binary = [(count, label) for label, count in counts.items() if label in (0, 1)]
    top_count, top_label = max(binary, default=(0, None))
    if counts[None] >= 2 or top_count < 2:
        majority = None
    else:
        majority = top_label
    unanimity = majority is not None and counts[majority] == 3 and len(valid) == 3
    agree = [float(j["confidence"]) for j in valid if j["label"] == majority] if majority is not None else []
    median_conf = median(agree) if agree else None
    contradictions = any(j.get("contradictory_evidence") for j in valid)
    verifier = verification or {"status": "not_run", "checks_passed": False}
    # A 2-of-3 vote can be accepted when both agreeing judgments are valid.
    # A third invalid/unknown judgment still makes this a non-unanimous case,
    # so it remains in the human review queue below.
    accepted = (majority is not None and top_count >= 2 and median_conf is not None
                and median_conf >= minimum_confidence and not contradictions
                and verifier.get("status") == "passed" and verifier.get("checks_passed"))
    # Any disagreement enters the human queue, even if a 2/3 candidate passes
    # the prespecified automatic evidence/confidence checks.
    review = (not unanimity or not accepted)
    final_label = majority if accepted else None
    return {
        "judge_majority_label": majority,
        "majority_type": "unanimous_candidate" if unanimity else ("majority_candidate" if majority is not None else "insufficient_agreement"),
        "agreeing_judges": top_count if majority is not None else 0,
        "valid_judges": len(valid),
        "median_agreeing_confidence": median_conf,
        "verification_status": verifier.get("status", "not_run"),
        "verification_checks_passed": bool(verifier.get("checks_passed")),
        "review_required": bool(review),
        "final_label": final_label,
    }
