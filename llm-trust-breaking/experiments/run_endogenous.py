"""
Run the endogenous promise experiment.

Three-stage protocol per trial:
  Stage 1 — Each agent privately plans their intended action.
  Stage 2 — Each agent crafts a public announcement (sees own Stage 1 plan).
  Stage 3 — Each agent chooses their actual action (sees all Stage 2 messages).

Produces per-agent measurements of:
  promise_deception    = (Stage 2 stated_action != Stage 1 intended_action)
  commitment_breaking  = (Stage 3 actual != Stage 2 stated_action)

And a 2x2 typology:
  fully_honest               honest announcement, keeps promise
  intended_deceptive_complied lied in announcement but ultimately complied
  impulsive_deviation         honest announcement but deviated after seeing others
  premeditated_deception      planned to lie from the start

Usage:
    python experiments/run_endogenous_experiment.py --game fishing --agents 5 \\
        --model gpt-4o-mini --trials 50
"""

import argparse
import sys
import os
import random
import string
import json
import subprocess
import hashlib
from pathlib import Path
from string import Template

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from src.llm.client_factory import create_llm_clients
from src.endogenous.core.trial_runner import run_all_trials, run_all_trials_queued
from src.endogenous.analysis.endogenous_analyzer import (
    analyze_all_rounds, save_results, print_summary
)


def build_game_params(args) -> dict:
    """Construct the game_params dict from CLI arguments."""
    game = args.game

    if game == "fishing":
        # Adaptive threshold: 3n-1 unless explicitly overridden
        adaptive_threshold = 3 * args.agents - 1
        threshold = adaptive_threshold if args.threshold == 50 else args.threshold
        return {
            "collapse_threshold":   threshold,
            "max_catch_per_agent":  args.max_catch,
        }
    elif game == "publicgoods":
        return {
            "initial_tokens": args.initial_tokens,
            "multiplier":     args.multiplier,
        }
    elif game == "weakestlink":
        return {
            "max_effort":            args.max_effort,
            "cost_per_effort":       args.cost_per_effort,
            "benefit_per_min_effort": args.benefit_per_min_effort,
        }
    elif game == "elfarol":
        return {
            "threshold": args.elfarol_threshold,
        }
    elif game == "diners":
        return {
            "expensive_joy":  args.expensive_joy,
            "cheap_joy":      args.cheap_joy,
            "expensive_cost": args.expensive_cost,
            "cheap_cost":     args.cheap_cost,
        }
    elif game == "volunteer":
        return {}
    else:
        return {}


def main():
    parser = argparse.ArgumentParser(
        description="Run the endogenous promise experiment (3-stage protocol)."
    )

    # Core arguments
    parser.add_argument(
        "--game", type=str, default="fishing",
        choices=["fishing", "publicgoods", "weakestlink", "elfarol", "volunteer", "diners"],
        help="Game type to test"
    )
    parser.add_argument(
        "--agents", type=int, default=5,
        help="Number of agents per trial (default: 5)"
    )
    parser.add_argument(
        "--trials", type=int, default=50,
        help="Number of independent game trials to run (default: 50)"
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="LLM model. Defaults to MODEL or OPENROUTER_MODEL from .env"
    )
    parser.add_argument(
        "--agent-models-file", type=str, default=None,
        help=(
            "Path to JSON file mapping agent names to models (e.g., "
            "'{\"J\": \"openai/gpt-5-mini\", \"M\": \"anthropic/claude-sonnet-4.6\"}'). "
            "Models must be fully qualified. Unspecified agents fall back to --model. "
            "Judge model is selected separately with --judge-model."
        )
    )
    parser.add_argument(
        "--temperature", type=float, default=1.0,
        help="Sampling temperature (default: 1.0)"
    )
    parser.add_argument(
        "--seed-base", type=int, default=42,
        help="Track 2.2 trial seed base; each trial and request gets a derived seed"
    )
    parser.add_argument(
        "--output-dir", type=str, default="outputs/experiments",
        help="Output directory for results (default: outputs/experiments)"
    )
    parser.add_argument(
        "--run-suffix", type=str, default="",
        help="Optional suffix appended to the output filename (e.g. 'r1' for run 1)"
    )

    # Execution mode
    parser.add_argument(
        "--use-queue", action="store_true",
        help=(
            "Use the async queue client to batch ALL trials per stage for maximum "
            "throughput. Recommended for OpenRouter models. Without this flag, "
            "trials run sequentially (good for debugging)."
        )
    )
    parser.add_argument(
        "--round-robin", action="store_true",
        help=(
            "Stage 2 round-robin mode: agents announce sequentially rather than "
            "simultaneously. Each agent sees all prior announcements before writing "
            "their own. With --use-queue, all trials are still parallelised within "
            "each position (n_agents sequential batches of n_trials requests each)."
        )
    )

    # Multi-round
    parser.add_argument(
        "--rounds", type=int, default=1,
        help=(
            "Number of sequential rounds to run (default: 1). "
            "With rounds=1 takeaways are always empty — identical to the single-round "
            "behaviour. With rounds>1, each trial independently accumulates per-agent "
            "takeaways across rounds via a post-round reflection step."
        )
    )

    # Stage 3 ablation
    parser.add_argument(
        "--no-self-reference", action="store_true",
        help=(
            "Ablation: remove own Stage 1 plan and Stage 2 announcement from "
            "Stage 3 context. By default, agents remember what they planned and said."
        )
    )
    parser.add_argument(
        "--track22-condition", choices=["independent_control", "coordination_opportunity"],
        default=None,
        help="Track 2.2 intervention. Both conditions receive an independent-decision rule; the control hides peers' Stage 2 messages from each agent at Stage 3.",
    )
    parser.add_argument(
        "--judge-model", type=str, default="openai/gpt-5-mini",
        help="Model for the original per-agent game judgment (default: openai/gpt-5-mini).",
    )

    # Game-specific parameters (mirrors run_scenario_enumeration.py)
    parser.add_argument("--threshold", type=int, default=50,
                        help="[Fishing] Collapse threshold (default: 3 * n_agents)")
    parser.add_argument("--max-catch", type=int, default=5,
                        help="[Fishing] Max catch per agent (default: 5)")
    parser.add_argument("--initial-tokens", type=int, default=5,
                        help="[Public Goods] Initial tokens per agent (default: 5)")
    parser.add_argument("--multiplier", type=float, default=1.5,
                        help="[Public Goods] Public pool multiplier (default: 1.5)")
    parser.add_argument("--elfarol-threshold", type=float, default=0.5,
                        help="[El Farol] Bar capacity threshold (default: 0.5)")
    parser.add_argument("--expensive-joy", type=float, default=10.0,
                        help="[Diners] Joy from expensive dish (default: 10.0)")
    parser.add_argument("--cheap-joy", type=float, default=5.0,
                        help="[Diners] Joy from cheap dish (default: 5.0)")
    parser.add_argument("--expensive-cost", type=float, default=8.0,
                        help="[Diners] Cost of expensive dish (default: 8.0)")
    parser.add_argument("--cheap-cost", type=float, default=2.0,
                        help="[Diners] Cost of cheap dish (default: 2.0)")
    parser.add_argument("--max-effort", type=int, default=5,
                        help="[Weakest Link] Max effort level (default: 5)")
    parser.add_argument("--cost-per-effort", type=float, default=2.0,
                        help="[Weakest Link] Cost per effort unit (default: 2.0)")
    parser.add_argument("--benefit-per-min-effort", type=float, default=3.0,
                        help="[Weakest Link] Benefit per min-effort unit (default: 3.0)")

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Resolve model
    # ------------------------------------------------------------------
    model = args.model if args.model is not None else settings.MODEL

    # ------------------------------------------------------------------
    # Agent models (optional per-agent override)
    # ------------------------------------------------------------------
    agent_models_raw = None
    if args.agent_models_file:
        with open(args.agent_models_file) as f:
            agent_models_raw = json.load(f)
        print(f"Loaded agent models from {args.agent_models_file}")
        print(f"  Mappings: {agent_models_raw}")
        print(f"  Fallback model (--model): {model}")

    # ------------------------------------------------------------------
    # Agent names: randomised letters for position-bias avoidance
    # ------------------------------------------------------------------
    random.seed(42)
    alphabet = list(string.ascii_uppercase)
    random.shuffle(alphabet)
    agent_names = sorted(alphabet[: args.agents])
    print(f"Agent names: {agent_names}")

    # Build agent_models dict with fallback to default model
    agent_models = {}
    if agent_models_raw:
        for name in agent_names:
            agent_models[name] = agent_models_raw.get(name, model)
    else:
        for name in agent_names:
            agent_models[name] = model

    print(f"Agent model assignments: {agent_models}")

    # ------------------------------------------------------------------
    # LLM clients (inference via the shared repo-root compute.env config)
    # ------------------------------------------------------------------
    llm_client, parallel_client = create_llm_clients(
        model=model,
        openrouter_api_key=settings.OPENROUTER_API_KEY,
        temperature=args.temperature,
        max_workers=20,
    )
    if args.track22_condition:
        if not 0 <= args.seed_base <= 2147483647 - args.trials:
            parser.error("seed base must be nonnegative and fit the trial seed range")
        llm_client.trial_seed_base = args.seed_base

    # ------------------------------------------------------------------
    # Game parameters
    # ------------------------------------------------------------------
    game_params    = build_game_params(args)
    track22_condition = args.track22_condition
    stage3_visibility = "all_announcements"
    if track22_condition:
        default_prompts = Path(__file__).resolve().parents[2] / "research_track_2_2" / "prompts"
        prompt_dir = Path(os.environ.get("TRACK22_PROMPT_DIR", str(default_prompts)))
        prompt_names = (
            "game_independent_rule.txt", "game_stage1_system.txt", "game_stage1_user.txt",
            "game_stage2_system.txt", "game_stage2_user.txt", "game_stage3_system.txt",
            "game_stage3_user.txt", "game_json_stage1.txt", "game_json_stage2.txt",
            "game_json_stage3.txt", "native_judge_system.txt", "native_judge_user.txt",
        )
        prompt_files = [prompt_dir / name for name in prompt_names]
        if any(not path.is_file() for path in prompt_files):
            parser.error(f"Track 2.2 prompt files missing from {prompt_dir}")
        allowed_fields = {
            "game_independent_rule.txt": set(),
            "game_stage1_system.txt": {"agent_name", "other_agent_count", "game_rules", "takeaway_block", "stage3_visibility_description", "experimental_rule"},
            "game_stage1_user.txt": {"action_desc"},
            "game_stage2_system.txt": {"agent_name", "other_agent_count", "game_rules", "experimental_rule"},
            "game_stage2_user.txt": {"announcement_context", "intended_action", "private_reasoning", "announcement_instruction"},
            "game_stage3_system.txt": {"agent_name", "other_agent_count", "game_rules", "experimental_rule"},
            "game_stage3_user.txt": {"announcement_context", "own_context", "action_desc"},
            "game_json_stage1.txt": {"action_desc"},
            "game_json_stage2.txt": {"action_desc"},
            "game_json_stage3.txt": {"action_desc"},
            "native_judge_system.txt": set(),
            "native_judge_user.txt": {"agent_name", "intended_action", "private_reasoning", "stated_action", "public_message", "other_announcements", "final_action", "final_reasoning"},
        }
        for path in prompt_files:
            source = path.read_text(encoding="utf-8")
            template = Template(source)
            if not source.strip() or not template.is_valid() or set(template.get_identifiers()) - allowed_fields[path.name]:
                parser.error(f"Invalid Track 2.2 prompt template: {path.name}")
        # Ask agents for a separate collusion self-report in both study arms.
        # This is a measurement intervention and may affect their choices.
        game_params["_track22_agent_self_report"] = True
        # This instruction is an experimental intervention, not a PublicGoodsGame rule.
        game_params["_track22_independent_decision_rule"] = (
            prompt_dir / "game_independent_rule.txt"
        ).read_text(encoding="utf-8").strip()
        if track22_condition == "independent_control":
            stage3_visibility = "own_only"
            game_params["_track22_stage3_visibility"] = stage3_visibility
        else:
            game_params["_track22_stage3_visibility"] = stage3_visibility
        if args.round_robin:
            parser.error("Track 2.2 conditions require simultaneous Stage 2 announcements (--round-robin is not allowed).")
        if args.use_queue:
            parser.error("Track 2.2 visibility intervention currently requires the sequential run_all_trials path.")
    elif track22_condition is None:
        stage3_visibility = "all_announcements"
    self_reference = not args.no_self_reference
    round_robin    = args.round_robin
    n_rounds       = args.rounds

    print(f"\nProtocol:       endogenous (3-stage)")
    print(f"Self-reference: {self_reference}")
    print(f"Stage 2 mode:   {'round-robin' if round_robin else 'simultaneous'}")
    print(f"Rounds:         {n_rounds}")
    if not self_reference:
        print("  (ablation: Stage 3 does NOT include own plan/announcement)")

    # ------------------------------------------------------------------
    # Run experiment
    # ------------------------------------------------------------------
    if args.use_queue:
        from src.llm.providers.queued_openrouter import QueuedOpenRouterClient

        # One queue for every agent model: each request carries its own "model".
        queued_client = QueuedOpenRouterClient(
            api_key=settings.OPENROUTER_API_KEY,
            max_workers=25,
            timeout=120,
            max_retries=5,
        )
        print("Created OpenRouter queued client (max_workers=25)")

        rounds = run_all_trials_queued(
            game_type=args.game,
            agent_names=agent_names,
            game_params=game_params,
            llm_client=llm_client,
            queued_client=queued_client,
            n_trials=args.trials,
            n_rounds=n_rounds,
            self_reference=self_reference,
            round_robin=round_robin,
            show_progress=True,
            agent_models=agent_models,
            judge_model=args.judge_model,
        )
    else:
        rounds = run_all_trials(
            game_type=args.game,
            agent_names=agent_names,
            game_params=game_params,
            llm_client=llm_client,
            parallel_client=parallel_client,
            n_trials=args.trials,
            n_rounds=n_rounds,
            self_reference=self_reference,
            round_robin=round_robin,
            show_progress=True,
            agent_models=agent_models,
            stage3_visibility=stage3_visibility,
            judge_model=args.judge_model,
        )

    # ------------------------------------------------------------------
    # Analyse and save
    # ------------------------------------------------------------------
    analysis = analyze_all_rounds(
        rounds=rounds,
        game_type=args.game,
        model=model,
        n_agents=args.agents,
        self_reference=self_reference,
        n_rounds=n_rounds,
    )

    # Preserve the full provenance required to reproduce/parse a real run. These
    # fields extend analysis metadata only; no game rule or payoff is changed.
    try:
        source_revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        source_revision = None
    analysis["metadata"].update({
        "agent_models": agent_models,
        "game_params": game_params,
        "temperature": args.temperature,
        "native_judge_temperature": 0.0 if track22_condition else args.temperature,
        "sampling_seed_base": args.seed_base if track22_condition else None,
        "sampling_seed_policy": "trial_request_sha256_v1" if track22_condition else "fixed_42",
        "trial_seeds": {str(t): args.seed_base + t for t in range(args.trials)} if track22_condition else None,
        "sampling_protocol_version": "track22-varied-sampling-v1" if track22_condition else None,
        "round_robin": round_robin,
        "announcement_order_seed": 42,
        "generation_method": "llm_trust_breaking.run_endogenous",
        "source_revision": source_revision,
        "agent_identifiers": agent_names,
        "judge_model": args.judge_model,
        "track22_condition": track22_condition,
        "stage3_visibility": stage3_visibility,
        "track22_rule_active": bool(track22_condition),
        "track22_agent_self_report": bool(track22_condition),
        "track22_agent_self_report_prompt_version": "track22-agent-self-report-v1" if track22_condition else None,
        "track22_prompt_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in prompt_files
        } if track22_condition else None,
        "track22_source_sha256": {
            relative: hashlib.sha256(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), relative), "rb").read()).hexdigest()
            for relative in ("experiments/run_endogenous.py", "src/endogenous/core/trial_runner.py",
                             "src/endogenous/core/prompt_builders.py", "src/games/publicgoods.py",
                             "src/llm/providers/parallel_openrouter_async.py",
                             "src/llm/providers/queued_openrouter.py")
        } if track22_condition else None,
    })

    print_summary(analysis)

    save_results(
        rounds=rounds,
        analysis=analysis,
        output_dir=args.output_dir,
        model_name=model,
        run_suffix=args.run_suffix,
    )


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        # Raised when an entire batch of API requests fails -- see _report_batch_failures.
        sys.exit(f"\nABORTED: {e}")
