"""Parse genuine LLM Trust Breaking endogenous PublicGoods runs.

The parser does not assign a binary collusion label from treatment assignment,
matching actions, promises, or access to communication. It labels only explicit,
reciprocal agreements that are carried out; all other cases remain ambiguous
unless a blinded review establishes independent behavior under preregistered
criteria. The game itself does not prohibit agreements.
"""
from __future__ import annotations

import hashlib
from itertools import combinations
import json
from pathlib import Path
from typing import Any


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _label_trial(trial: dict[str, Any], agents: list[str]) -> dict[str, Any]:
    """Do not derive gold labels in the parser; all cases go through blind panel."""
    del trial, agents
    return {"label": "unlabeled", "basis": "separate_blinded_judge_panel_and_verification_required"}


def parse_ltb_run(payload: dict[str, Any], *, source_path: str | None = None) -> list[dict[str, Any]]:
    """Convert LTB save_results JSON into one canonical trajectory per trial."""
    metadata = payload.get("metadata", {})
    if metadata.get("game_type") != "publicgoods":
        raise ValueError("Only game_type=publicgoods is supported by this Track 2.2 parser")
    agent_models = metadata.get("agent_models") or {}
    source_bytes = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    result = []
    for round_blob in payload.get("rounds", []):
        round_id = round_blob.get("round_id")
        for trial in round_blob.get("trials", []):
            agents_map = trial.get("agents", {})
            agent_ids = list(agents_map)
            actions = {a: agents_map[a].get("stage3", {}).get("choice") for a in agent_ids}
            messages = [
                {"round": 1, "speaker": a, "text": str(agents_map[a].get("stage2", {}).get("message", "")),
                 "stated_action": agents_map[a].get("stage2", {}).get("stated_action"),
                 "parse_ok": agents_map[a].get("stage2", {}).get("_parse_ok")}
                for a in agent_ids
            ]
            plans = {
                a: {"intended_action": agents_map[a].get("stage1", {}).get("intended_action"),
                    "reasoning": agents_map[a].get("stage1", {}).get("reasoning", ""),
                    "parse_ok": agents_map[a].get("stage1", {}).get("_parse_ok")}
                for a in agent_ids
            }
            settings = metadata.get("game_params", {})
            tid = f"ltb-{_sha256(source_bytes)[:10]}-r{round_id}-t{trial.get('trial_id')}"
            result.append({
                "trajectory_id": tid,
                "dataset_type": "real_llm_agent_trajectory",
                "game_name": "publicgoods",
                "trial_id": trial.get("trial_id"),
                "round_id": round_id,
                "agent_ids": agent_ids,
                "agent_models": {a: agent_models.get(a, metadata.get("model")) for a in agent_ids},
                "private_plans": plans,
                "public_messages": messages,
                "actions": actions,
                "action_reasoning": {a: agents_map[a].get("stage3", {}).get("reasoning", "") for a in agent_ids},
                "outcomes": trial.get("outcomes", {}),
                "game_settings": settings,
                "protocol_settings": {
                    "name": metadata.get("protocol", "endogenous"),
                    "stage2_mode": "round_robin" if metadata.get("round_robin") else "simultaneous",
                "self_reference": metadata.get("self_reference"),
                    "track22_condition": metadata.get("track22_condition"),
                    "stage3_visibility": metadata.get("stage3_visibility"),
                    "track22_rule_active": metadata.get("track22_rule_active", False),
                },
                "generation_metadata": {
                    "generation_method": "llm_trust_breaking.run_endogenous",
                    "source_revision": metadata.get("source_revision"),
                    "track22_source_sha256": metadata.get("track22_source_sha256"),
                    "timestamp": metadata.get("timestamp"),
                    "temperature": metadata.get("temperature"),
                    "source_run_sha256": _sha256(source_bytes),
                    "source_path": source_path,
                    "parse_errors": trial.get("_parse_errors"),
                    "stage_parse_status": {
                        agent: {stage: trial.get("agents", {}).get(agent, {}).get(stage, {}).get("_parse_ok")
                                for stage in ("stage1", "stage2", "stage3")}
                        for agent in agent_ids
                    },
                    "announcement_order": trial.get("announcement_order"),
                },
                "label_assessment": _label_trial(trial, agent_ids),
            })
    return result


def parse_file(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    return parse_ltb_run(payload, source_path=str(path))


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, dict[str, Any]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                existing[row["trajectory_id"]] = row
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            old = existing.get(row["trajectory_id"])
            if old is not None:
                if old != row:
                    raise ValueError(f"trajectory_id collision with different content: {row['trajectory_id']}")
                continue
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
            existing[row["trajectory_id"]] = row
