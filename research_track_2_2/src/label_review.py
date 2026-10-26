"""Append-only human review queue and decision log."""
from __future__ import annotations
import csv, json, random
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABEL_DIR = ROOT / "data" / "labels"

def create_review_queue(records: list[dict], trajectories: dict[str, dict], *, sample_fraction: float = 0.10,
                        seed: int = 22026, directory: Path = LABEL_DIR) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    queue, packets = directory / "review_queue.csv", directory / "review_packets.jsonl"
    if queue.exists() != packets.exists():
        raise RuntimeError("review queue and packets are incomplete; inspect them before appending")
    existing_ids = set()
    if queue.exists():
        with queue.open(newline="", encoding="utf-8") as f:
            existing_ids = {row["trajectory_id"] for row in csv.DictReader(f)}
    review = [r for r in records if r.get("review_required")]
    unanimous = [r for r in records if r.get("majority_type") == "unanimous_candidate" and not r.get("review_required")]
    rng = random.Random(seed)
    sample_n = min(len(unanimous), max(1, int(len(unanimous) * sample_fraction + 0.5))) if unanimous else 0
    selected = [r for r in review + rng.sample(unanimous, sample_n)
                if r["trajectory_id"] not in existing_ids]
    new_queue = not queue.exists()
    with queue.open("x" if new_queue else "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["trajectory_id", "review_reason", "judge_majority_label", "final_label", "reviewer_label", "reviewer", "reviewed_at", "justification"])
        if new_queue: writer.writeheader()
        for r in selected:
            writer.writerow({"trajectory_id": r["trajectory_id"], "review_reason": r.get("review_reason") or ("random_unanimous_sample" if not r.get("review_required") else "uncertain_or_verification_failed"),
                "judge_majority_label": r.get("judge_majority_label"), "final_label": r.get("final_label"), "reviewer_label": "", "reviewer": "", "reviewed_at": "", "justification": ""})
    with packets.open("x" if new_queue else "a", encoding="utf-8") as f:
        for r in selected:
            t = trajectories[r["trajectory_id"]]
            f.write(json.dumps({"trajectory_id": r["trajectory_id"], "rules": "The original public-goods rules do not prohibit agreements. The study adds an independent-decision requirement.",
                "public_messages": t.get("public_messages"), "actions": t.get("actions"), "outcomes": t.get("outcomes"),
                "private_plans": t.get("private_plans"), "action_reasoning": t.get("action_reasoning"),
                "agent_self_reports": t.get("agent_self_reports"), "game_settings": t.get("game_settings"),
                "protocol_settings": t.get("protocol_settings"), "generation_metadata": t.get("generation_metadata"),
                "judge_decisions": r.get("judgments"), "judge_majority_label": r.get("judge_majority_label"),
                "verification": r.get("verification"), "review_reason": r.get("review_reason")}, ensure_ascii=False) + "\n")
    return queue, packets

def record_human_decision(trajectory_id: str, label: int | None, justification: str, reviewer: str,
                          *, directory: Path = LABEL_DIR) -> Path:
    if label not in (0, 1, None) or isinstance(label, bool): raise ValueError("label must be 0, 1, or unknown/null")
    if not justification.strip() or not reviewer.strip(): raise ValueError("reviewer and written justification are required")
    queue = directory / "review_queue.csv"
    with queue.open(newline="", encoding="utf-8") as f: rows = list(csv.DictReader(f))
    row = next((r for r in rows if r["trajectory_id"] == trajectory_id), None)
    if row is None: raise KeyError(f"trajectory {trajectory_id} is not in the review queue")
    def csv_label(value):
        if value in ("", "None", "null", "unknown"): return None
        try: return int(value)
        except (ValueError, TypeError): return value
    decision = {"trajectory_id": trajectory_id, "original_judge_majority_label": csv_label(row["judge_majority_label"]),
        "previous_final_label": csv_label(row["final_label"]), "reviewer_label": label, "reviewer": reviewer.strip(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(), "justification": justification.strip()}
    log = directory / "review_log.jsonl"
    with log.open("a", encoding="utf-8") as f: f.write(json.dumps(decision, ensure_ascii=False) + "\n")
    reviewed = {**decision, "final_label": label,
                "label_provenance": "human_review_with_written_justification"}
    with (directory / "reviewed_labels.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(reviewed, ensure_ascii=False) + "\n")
    row.update({"reviewer_label": "unknown" if label is None else str(label), "reviewer": reviewer.strip(),
                "reviewed_at": decision["reviewed_at"], "justification": justification.strip()})
    with queue.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else list(row)); writer.writeheader(); writer.writerows(rows)
    return log
