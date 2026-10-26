"""Guarded bridge to the actual llm-trust-breaking endogenous runner.

No request is sent unless the caller sets execute_paid=True and confirms a
maximum estimate. The wrapper invokes the starter project's own runner and
never reimplements stages, game actions, or payoff calculations.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .real_trajectories import parse_file, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(os.getenv("TRACK22_REPO_ROOT", str(ROOT.parent)))
STARTER = Path(os.getenv("LLM_TRUST_BREAKING_ROOT", str(REPO / "llm-trust-breaking")))
UTILITY = Path(os.getenv("POSEIDON_UTIL_ROOT", str(REPO / "util")))
RUNNER = STARTER / "experiments" / "run_endogenous.py"
LLM_DATA = ROOT / "data" / "llm_agents"
RESULTS_DIR = ROOT / "results" / "llm_agents"
MODEL_CONFIG_PATH = ROOT / "configs" / "game_models.json"
DEFAULT_GAME_TEMPERATURE = 0.7
DEFAULT_SEED_BASE = 42


def load_game_model_config(path: Path = MODEL_CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    models = config.get("models", {})
    if config.get("default_agent_model") not in models or config.get("default_judge_model") not in models:
        raise ValueError("game model config defaults must reference entries in models")
    for model_id, model in models.items():
        if not isinstance(model.get("input_usd_per_million"), (int, float)) or not isinstance(model.get("output_usd_per_million"), (int, float)):
            raise ValueError(f"model {model_id!r} needs numeric input/output prices")
        if min(model["input_usd_per_million"], model["output_usd_per_million"]) < 0:
            raise ValueError(f"model {model_id!r} has negative token pricing")
        if not isinstance(model.get("roles"), list):
            raise ValueError(f"model {model_id!r} needs a roles list")
    return config


GAME_MODEL_CONFIG = load_game_model_config()
DEFAULT_AGENT_MODEL = GAME_MODEL_CONFIG["default_agent_model"]
DEFAULT_JUDGE_MODEL = GAME_MODEL_CONFIG["default_judge_model"]
GAME_MODELS = GAME_MODEL_CONFIG["models"]
AGENT_MODEL_PRICES = {
    model_id: (float(model["input_usd_per_million"]), float(model["output_usd_per_million"]))
    for model_id, model in GAME_MODELS.items() if "agent" in model["roles"]
}
JUDGE_MODEL_PRICES = {
    model_id: (float(model["input_usd_per_million"]), float(model["output_usd_per_million"]))
    for model_id, model in GAME_MODELS.items() if "game_judge" in model["roles"]
}


def summarize_raw_calls(raw_calls_dir: Path) -> dict[str, Any]:
    """Summarize provider-reported usage from captured HTTP attempts; never estimate actuals."""
    calls_path = raw_calls_dir / "calls.jsonl"
    calls = [json.loads(line) for line in calls_path.read_text(encoding="utf-8").splitlines()
             if line.strip()] if calls_path.exists() else []
    responses = [row for row in calls if row.get("http_status") is not None]
    usage_rows = [row.get("usage") for row in calls if isinstance(row.get("usage"), dict)]

    def sum_field(name: str) -> int | None:
        values = [usage[name] for usage in usage_rows if isinstance(usage.get(name), (int, float))]
        return int(sum(values)) if values else None

    costs = [usage["cost"] for usage in usage_rows if isinstance(usage.get("cost"), (int, float))]
    successful = [row for row in responses if 200 <= row["http_status"] < 300]
    usage_complete = bool(successful) and all(
        isinstance(row.get("usage"), dict)
        and isinstance(row["usage"].get("prompt_tokens"), (int, float))
        and isinstance(row["usage"].get("completion_tokens"), (int, float))
        and isinstance(row["usage"].get("cost"), (int, float))
        for row in successful
    )
    summary = {
        "http_attempts_recorded": len(calls),
        "http_responses_received": len(responses),
        "successful_http_responses": len(successful),
        "failed_http_responses": sum(not (200 <= row["http_status"] < 300) for row in responses),
        "provider_usage_records": len(usage_rows),
        "provider_reported_prompt_tokens": sum_field("prompt_tokens"),
        "provider_reported_completion_tokens": sum_field("completion_tokens"),
        "provider_reported_total_tokens": sum_field("total_tokens"),
        "provider_reported_cost_usd": round(sum(costs), 8) if costs else None,
        "provider_usage_status": "complete" if usage_complete else ("partial" if usage_rows else "unavailable"),
        "raw_calls_file": "calls.jsonl",
    }
    usage_path = raw_calls_dir / "usage.json"
    fd = os.open(usage_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return summary


def conservative_smoke_estimate(agents: int = 2, trials: int = 1,
                                model: str = DEFAULT_AGENT_MODEL,
                                judge_model: str = DEFAULT_JUDGE_MODEL) -> dict[str, Any]:
    """Game-only preflight using independently configurable agent and judge models."""
    if agents < 2 or trials < 1:
        raise ValueError("agents must be >= 2 and trials >= 1")
    if model not in AGENT_MODEL_PRICES:
        raise ValueError(f"No reviewed price estimate for agent model {model!r}; supported: {', '.join(AGENT_MODEL_PRICES)}")
    agent_input_rate, agent_output_rate = AGENT_MODEL_PRICES[model]
    if judge_model not in JUDGE_MODEL_PRICES:
        raise ValueError(f"No reviewed price estimate for game-judge model {judge_model!r}; supported: {', '.join(JUDGE_MODEL_PRICES)}")
    judge_input_rate, judge_output_rate = JUDGE_MODEL_PRICES[judge_model]
    game_calls = (3 * agents + agents) * trials  # 3 stages plus LLM judge per agent
    attempts = 3  # starter async client retries at most 3 times per request
    agent_calls = 3 * agents * trials * attempts
    judge_calls = agents * trials * attempts
    input_usd = agent_calls * 5000 * agent_input_rate / 1_000_000 + judge_calls * 5000 * judge_input_rate / 1_000_000
    output_usd = agent_calls * 2000 * agent_output_rate / 1_000_000 + judge_calls * 2000 * judge_output_rate / 1_000_000
    return {
        "agent_model": model,
        "native_judge_model": judge_model,
        "game_requests": game_calls,
        "agent_stage_requests": 3 * agents * trials,
        "original_ltb_judge_requests": agents * trials,
        "max_http_attempts_including_retries": game_calls * attempts,
        "input_tokens_reserved": (agent_calls + judge_calls) * 5000,
        "output_tokens_reserved": (agent_calls + judge_calls) * 2000,
        "estimated_cost_usd": round(input_usd + output_usd, 4),
        "assumptions": f"agent stages {model} at ${agent_input_rate}/${agent_output_rate} per million; native LTB judge {judge_model} at ${judge_input_rate}/${judge_output_rate}; 3 tries/request; 5k input + 2k output per attempt; monitor calls excluded",
    }


def _openrouter_key() -> str | None:
    """Read the key without returning it to logs or command-line arguments."""
    key = os.getenv("OPENROUTER_API_KEY")
    if key:
        return key
    for config_path in (REPO / "compute.env", ROOT / ".env"):
        if not config_path.is_file():
            continue
        for line in config_path.read_text().splitlines():
            match = re.match(r"\s*(?:export\s+)?OPENROUTER_API_KEY\s*=\s*(.*?)\s*$", line)
            if match:
                value = match.group(1).strip().strip("\"'")
                if value and not value.startswith("#"):
                    return value
    return None


def write_readable_run_bundle(*, raw_path: Path, trajectories: list[dict], run_id: str,
                              condition: str | None, agent_model: str, judge_model: str,
                              estimate: dict[str, Any], output_dir: Path = RESULTS_DIR,
                              folder: Path | None = None) -> Path:
    """Create a new timestamped folder with human- and machine-readable results."""
    folder = folder or output_dir / f"{run_id}_{condition or 'unconditioned'}"
    if folder.exists():
        if not folder.is_dir() or any(p.name != "raw_calls" for p in folder.iterdir()):
            raise FileExistsError(f"result folder already contains data: {folder}")
        (folder / "raw_calls").mkdir(mode=0o700, exist_ok=True)
    else:
        folder.mkdir(parents=True, exist_ok=False, mode=0o700)
        (folder / "raw_calls").mkdir(mode=0o700)
    raw_usage = summarize_raw_calls(folder / "raw_calls")
    shutil.copy2(raw_path, folder / "source_run.json")
    source_payload = json.loads(raw_path.read_text(encoding="utf-8"))
    metadata = source_payload.get("metadata", {})
    sampling = {key: metadata.get(key) for key in (
        "temperature", "native_judge_temperature", "sampling_seed_base",
        "sampling_seed_policy", "sampling_protocol_version", "trial_seeds")}
    unique_content = {json.dumps({key: row.get(key) for key in (
        "private_plans", "public_messages", "actions", "action_reasoning", "agent_self_reports")},
        sort_keys=True, ensure_ascii=False) for row in trajectories}
    diversity = {"trajectory_count": len(trajectories), "unique_game_content_count": len(unique_content),
                 "repeated_game_content_count": len(trajectories) - len(unique_content)}
    source_trials = {
        (round_row.get("round_id"), trial.get("trial_id")): trial
        for round_row in source_payload.get("rounds", [])
        for trial in round_row.get("trials", [])
    }
    with (folder / "trajectories.jsonl").open("x", encoding="utf-8") as handle:
        for trajectory in trajectories:
            handle.write(json.dumps(trajectory, ensure_ascii=False, sort_keys=True) + "\n")

    lines = [
        f"# Public-goods pilot run: {condition or 'unconditioned'}",
        "",
        f"- Run ID: `{run_id}`",
        f"- Agent model: `{agent_model}`",
        f"- Original game-judge model: `{judge_model}`",
        f"- Trajectories: {len(trajectories)}",
        f"- Agent temperature: {sampling['temperature']}; trial seed base: {sampling['sampling_seed_base']}; seed policy: {sampling['sampling_seed_policy']}",
        f"- Unique game records: {len(unique_content)}/{len(trajectories)}; repeated content: {diversity['repeated_game_content_count']}. Different seeds do not guarantee independent or different behavior.",
        f"- Estimated inference cost: ${estimate['estimated_cost_usd']:.4f} (estimate only)",
        f"- Expected logical requests: {estimate['game_requests']}; retry reserve: up to {estimate['max_http_attempts_including_retries']} HTTP attempts",
        f"- Actual HTTP attempts captured: {raw_usage['http_attempts_recorded']}",
        f"- Provider-reported usage: {raw_usage['provider_usage_status']}; input tokens={raw_usage['provider_reported_prompt_tokens']}; output tokens={raw_usage['provider_reported_completion_tokens']}; cost USD={raw_usage['provider_reported_cost_usd']}",
        "- Raw request/response attempts and usage are in `raw_calls/calls.jsonl` and `raw_calls/usage.json`; credentials are not recorded.",
        "- Research label judges and M1–M4 monitors: not run in this game-generation stage.",
        "",
        "## Game records",
        "",
    ]
    summary = {
        "run_id": run_id, "condition": condition, "agent_model": agent_model,
        "game_judge_model": judge_model, "trajectory_count": len(trajectories),
        "sampling_settings": sampling, "diversity": diversity,
        "expected_logical_requests": estimate["game_requests"],
        "reserved_max_http_attempts": estimate["max_http_attempts_including_retries"],
        "estimated_cost_usd": estimate["estimated_cost_usd"],
        "actual_api_usage": raw_usage,
        "label_judges_run": False, "monitors_run": False,
        "source_file": str(raw_path),
    }
    for index, trajectory in enumerate(trajectories, start=1):
        lines.extend([f"### Trajectory {index}: `{trajectory.get('trajectory_id')}`", ""])
        source_trial = source_trials.get((trajectory.get("round_id"), trajectory.get("trial_id")), {})
        for label, agent_id in zip(("Agent A", "Agent B"), trajectory.get("agent_ids", [])):
            plan = trajectory.get("private_plans", {}).get(agent_id, {})
            message = next((m for m in trajectory.get("public_messages", []) if m.get("speaker") == agent_id), {})
            actual = trajectory.get("actions", {}).get(agent_id)
            game_judgment = source_trial.get("agents", {}).get(agent_id, {}).get("judge", {})
            lines.extend([
                f"#### {label} (runner ID `{agent_id}`)", "",
                f"- Plan: intended action **{plan.get('intended_action', 'missing')}**. {plan.get('reasoning', '')}",
                f"- Announcement: {message.get('text', 'missing')}",
                f"- Actual action: **{actual if actual is not None else 'missing'}** tokens.",
                f"- Original game-judge result: {game_judgment.get('primary_label', 'not recorded')} (confidence {game_judgment.get('confidence', 'not recorded')}/5). This is not the research label.",
                "",
            ])
        outcomes = trajectory.get("outcomes", {})
        lines.extend(["**Outcome:**", "", f"- Actions: `{json.dumps(trajectory.get('actions', {}), ensure_ascii=False)}`",
                      f"- Payouts: `{json.dumps(outcomes.get('payoffs', {}), ensure_ascii=False)}`",
                      f"- Game record: {outcomes.get('description', '')}", ""])
        parse_errors = trajectory.get("generation_metadata", {}).get("parse_errors")
        parse_status = trajectory.get("generation_metadata", {}).get("stage_parse_status", {})
        complete = parse_errors == 0 and all(
            parse_status.get(agent, {}).get(stage) is True
            for agent in trajectory.get("agent_ids", [])
            for stage in ("stage1", "stage2", "stage3")
        )
        if trajectory.get("protocol_settings", {}).get("agent_self_report_active"):
            complete = complete and all(
                trajectory.get("agent_self_reports", {}).get(agent, {}).get("parse_ok") is True
                and str(trajectory.get("action_reasoning", {}).get(agent, "")).strip()
                for agent in trajectory.get("agent_ids", [])
            )
        lines.extend([f"**Trajectory completeness:** {'Passed' if complete else 'Needs review'}; parse errors: {parse_errors}.", ""])
        summary.setdefault("trajectory_checks", []).append({
            "trajectory_id": trajectory.get("trajectory_id"), "complete": complete,
            "parse_errors": parse_errors, "stage_parse_status": parse_status,
        })
    (folder / "README.md").write_text("\n".join(lines), encoding="utf-8")
    with (folder / "summary.json").open("x", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return folder


def run_real_game(*, agents: int = 2, trials: int = 1, model: str = DEFAULT_AGENT_MODEL,
                  judge_model: str = DEFAULT_JUDGE_MODEL,
                  temperature: float = DEFAULT_GAME_TEMPERATURE, seed_base: int = DEFAULT_SEED_BASE,
                  max_cost_usd: float | None = None,
                  execute_paid: bool = False, round_robin: bool = False,
                  condition: str | None = None) -> Path | dict[str, Any]:
    if not math.isfinite(temperature) or not 0 <= temperature <= 2:
        raise ValueError("temperature must be between 0 and 2")
    if not 0 <= seed_base <= 2147483647 - trials:
        raise ValueError("seed base must be nonnegative and fit the trial seed range")
    estimate = conservative_smoke_estimate(agents, trials, model, judge_model)
    if not execute_paid:
        return {"status": "preflight_only", "condition": condition,
                "agent_temperature": temperature, "seed_base": seed_base,
                "sampling_seed_policy": "trial_request_sha256_v1" if condition else "fixed_42",
                **estimate}
    if condition not in (None, "independent_control", "coordination_opportunity"):
        raise ValueError("condition must be independent_control or coordination_opportunity")
    if condition and round_robin:
        raise ValueError("Track 2.2 controlled runs require simultaneous Stage 2")
    if max_cost_usd is None or max_cost_usd < estimate["estimated_cost_usd"]:
        raise ValueError(f"Explicit --max-cost-usd must be >= ${estimate['estimated_cost_usd']:.4f}")
    if not RUNNER.is_file():
        raise FileNotFoundError(f"Starter runner not found: {RUNNER}")
    openrouter_key = _openrouter_key()
    if not openrouter_key or openrouter_key == "your-openrouter-key-here":
        raise RuntimeError("No usable OpenRouter key found in OPENROUTER_API_KEY or compute.env; no request made")
    # Do not inspect, echo, or pass API keys on the command line. The starter's
    # shared poseidon_compute config reads the existing compute.env/environment.
    environment = os.environ.copy()
    # Match the price estimate's provider and prevent a shared LLM_MODEL override
    # from silently changing the model. This puts the key only in child-process
    # environment memory; it is never written to argv, files, or logs here.
    environment.pop("LLM_MODEL", None)
    environment["LLM_BASE_URL"] = "https://openrouter.ai/api/v1"
    environment["LLM_API_KEY"] = openrouter_key
    environment["OPENROUTER_MODEL"] = model
    if condition:
        environment["TRACK22_PROMPT_DIR"] = str(ROOT / "prompts")
    else:
        environment.pop("TRACK22_PROMPT_DIR", None)
    utility_path = str(UTILITY)
    environment["PYTHONPATH"] = utility_path + os.pathsep + environment.get("PYTHONPATH", "")
    source_dir = LLM_DATA / "source_runs"
    source_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    result_folder = RESULTS_DIR / f"{run_id}_{condition or 'unconditioned'}"
    result_folder.mkdir(parents=True, exist_ok=False, mode=0o700)
    raw_calls_dir = result_folder / "raw_calls"
    raw_calls_dir.mkdir(mode=0o700)
    calls_path = raw_calls_dir / "calls.jsonl"
    fd = os.open(calls_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    environment["TRACK22_RAW_CALLS_DIR"] = str(raw_calls_dir)
    environment["TRACK22_RUN_ID"] = run_id
    command = [sys.executable, str(RUNNER), "--game", "publicgoods", "--agents", str(agents),
               "--trials", str(trials), "--rounds", "1", "--model", model, "--judge-model", judge_model,
               "--temperature", str(temperature), "--seed-base", str(seed_base),
               "--output-dir", str(source_dir), "--run-suffix", run_id]
    if condition:
        command.extend(["--track22-condition", condition])
    if round_robin:
        command.append("--round-robin")
    completed = subprocess.run(command, cwd=STARTER, env=environment, text=True, capture_output=True)
    if completed.returncode:
        summarize_raw_calls(raw_calls_dir)
        (result_folder / "run_status.json").write_text(json.dumps({
            "status": "failed", "exit_code": completed.returncode,
            "stderr_tail": completed.stderr[-2000:],
        }, indent=2), encoding="utf-8")
        raise RuntimeError(f"llm-trust-breaking runner failed (exit {completed.returncode}):\n{completed.stderr[-4000:]}")
    safe_model = model.replace("/", "_").replace(":", "_")
    # The starter runner's save_results() names files with its run_suffix only;
    # the condition is recorded in JSON metadata, not in the filename.
    raw_path = source_dir / "publicgoods" / f"{agents}agents" / f"{safe_model}_endogenous_{run_id}.json"
    if not raw_path.is_file():
        summarize_raw_calls(raw_calls_dir)
        raise RuntimeError("Runner succeeded but did not produce the expected source-run JSON")
    rows = parse_file(raw_path)
    write_jsonl(rows, LLM_DATA / "trajectories.jsonl")
    bundle = write_readable_run_bundle(raw_path=raw_path, trajectories=rows, run_id=run_id,
                                       condition=condition, agent_model=model,
                                       judge_model=judge_model, estimate=estimate,
                                       folder=result_folder)
    return {"status": "completed", "source_run": str(raw_path),
            "results_folder": str(bundle), "trajectory_count": len(rows),
            "estimated_cost_usd": estimate["estimated_cost_usd"]}
