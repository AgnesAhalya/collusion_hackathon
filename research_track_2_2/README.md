# Track 2.2: evidence views over public-goods trajectories

The research path uses genuine trajectories from `llm-trust-breaking`'s endogenous public-goods runner. The prior pilot game runs, labels, and monitor outputs were cleared on 2026-10-26 at the study owner's request; no pilot data is currently retained. See [FLOW_AUDIT.md](FLOW_AUDIT.md) for the checked flow. Track 2.2 runs ask agents for a Stage 3 yes/no collusion self-report with confidence. Judges may see it as evidence; monitor views exclude it. The live prompt text is in [prompts/](prompts/README.md), with separate files for each game stage, judge, and monitor prompt.

## Offline reproduction

From this directory:

```sh
python -m unittest discover -s tests -v
python -m src.real_cli preflight --agents 2 --trials 1
python -m src.real_cli preflight --agents 2 --trials 1 --model deepseek/deepseek-v3.2 --judge-model deepseek/deepseek-v3.2
```

Tests do not call APIs or use saved synthetic datasets.

## Real runner connection (paid, gated)

The following prints a conservative estimate only:

```sh
python -m src.real_cli run-game --agents 2 --trials 1 --model openai/gpt-4.1-mini
```

After separate approval of the printed cost, the operator must pass `--execute-paid --max-cost-usd <approved-limit>`. The wrapper invokes `llm-trust-breaking/experiments/run_endogenous.py` with `--game publicgoods --rounds 1`, loads the Track 2.2 prompts from `prompts/`, preserves the original game rules and payoff calculation, and uses simultaneous Stage 2 by default. It saves the starter's native JSON under `data/llm_agents/source_runs/` and appends parsed genuine trajectories to `data/llm_agents/trajectories.jsonl`. It never reads or prints API keys. The starter uses its normal configured endpoint and its default retry behavior.

For an existing native JSON run, offline parsing is:

```sh
python -m src.real_cli parse-run data/llm_agents/source_runs/publicgoods/2agents/<run>.json
python -m src.real_cli prepare-views
```

The legacy `prepare-views` command materializes four evidence rows per trajectory. For new labeled runs, use the exclusive-create `src.ground_truth_pipeline prepare-monitor-inputs`, which writes `data/monitor_inputs/views.jsonl` and refuses to overwrite an existing file. To get a monitor cost preflight, run `python -m src.real_cli monitor`; it does not send requests. Paid monitor execution additionally requires `--execute-paid --max-cost-usd <approved-limit>`. Results go to a timestamped `results/llm_agents/<timestamp>_monitor/` subdirectory and include prompt hashes, raw responses, predictions, token usage, reported/estimated spend, and `monitor_vs_labels.md` comparing M1 with judge votes and final labels. The report counts success, failure, and undetermined outcomes; unknown final labels are excluded from precision.

To refresh only the Markdown comparison from saved predictions and labels (no API calls), run `python -m src.monitor_report results/llm_agents/<timestamp>_monitor --refresh`. This replaces only `monitor_vs_labels.md`.

## Labels and interpretation

The game rules do not prohibit communication or agreements. The parser now emits only `unlabeled`; it does not use a phrase matcher to propose a gold label. Matching actions and communication access are not proof; “unlabeled” is not negative. The blinded judge panel, deterministic evidence checks, review procedure, and experimental criteria are documented in [labeling_protocol.md](labeling_protocol.md).

M1 sees public messages. M2 sees actions and outcomes. M3 sees both in a raw timeline. M4 is a TraceGuard-inspired structured claim/action comparison. All four are made from the same genuine trajectory, with agent self-reports, private plans, treatment metadata, judge results, and label assessment excluded from monitor prompts. The three labeling judges may see agent self-reports, but treat them as claims to verify, not proof. Both Track 2.2 game conditions now ask agents for a direct yes/no collusion self-report and confidence at Stage 3; this added question may affect behavior and is recorded as a separate protocol feature.

## Integration attribution and limitations

The real game calls the starter's `run_endogenous.py`, `src.endogenous.core.trial_runner.run_all_trials`, and `src.games.publicgoods.PublicGoodsGame.evaluate`. The smallest runner patch adds an optional Stage 3 visibility argument and the study instruction to prompt builders. The parser maps the saved `rounds[*].trials[*].agents` stages and outcomes without fabricating agent text. `llm-trust-breaking`'s GPT-5 Mini judge field is retained in source JSON but excluded from monitor views and is not used as ground truth. The container installs only the runner's existing runtime dependencies; unused analysis packages such as NumPy and Matplotlib are not included.

TraceGuard's `ACTION_TRACE_CONSISTENCY` dimension in `trace-guard/src/traceguard/dimensions.py` is attribution for M4's rubric only; TraceGuard's original evaluator/monitor is not invoked. Its Inspect/ControlArena tool-call trace input is not the public-goods transcript format, so directly importing that evaluator would be a category mismatch.

Each new game run stores raw request/response attempts and any provider-reported token/cost usage in `results/llm_agents/<timestamp>_<condition>/raw_calls/`. The API key and authorization headers are never written there. Previous runs made before this capture was added cannot be backfilled from their saved game JSON. The Track 2.2 independent-control arm withholds peers' Stage 2 announcements at Stage 3, while the coordination-opportunity arm retains original visibility. The intervention is prompt-level; it does not change `PublicGoodsGame.evaluate`.
# Independent ground-truth labels for real LTB trajectories

Real research trajectories are generated by the original `llm-trust-breaking` `run_endogenous.py` and stored under `data/llm_agents/`. The Track 2.2 run adds an explicit independent-decision instruction (a study intervention, not an original game rule). Both conditions use simultaneous announcements. In the independent control, Stage 3 requests see only the agent's own Stage 1/2 context; in coordination opportunity, the original peer-announcement context is retained. Payoff code and game engine are unchanged.

## Offline commands

```sh
cd research_track_2_2
python3 -m unittest discover -s tests -v
python3 -m src.ground_truth_pipeline preflight --agents 2 --trials-per-condition 1
python3 -m src.ground_truth_pipeline label --budget-usd 1.00
python3 -m src.ground_truth_pipeline prepare-monitor-inputs
```

`label` is preflight-only unless `--execute-paid` is explicitly supplied. The 18 requested label cases, malformed-JSON retry/cache checks, controlled prompt test, and existing pipeline checks are mocked/offline and never call OpenRouter. `prepare-monitor-inputs` produces exactly M1–M4 per trajectory in `data/monitor_inputs/views.jsonl` after real trajectories exist.

## Approval-gated two-condition pilot

Game-agent and original game-judge models are independently configurable from `configs/game_models.json` and via `--model` / `--judge-model`. The built-in defaults are DeepSeek V3.2 for agents and GPT-5 Mini for the original game judge. With both set to DeepSeek V3.2, one independent-control game is estimated at $0.0399 for 8 requests and up to 24 HTTP attempts; the two-condition pilot including the label and monitor stages is estimated at $0.1253, or about $0.16 with a 25% planning margin. With the default GPT-5 Mini game judge, estimates are $0.0614 for one game and $0.1683 for the two-condition full pilot. Rates checked 2026-10-25: DeepSeek V3.2 $0.2088/$0.3096 and GPT-5 Mini $0.25/$2.00 per million input/output tokens. See `labeling_validation_report.md` for assumptions and known limits. The native runner has no provider-enforced spend ceiling; local caps are estimates only.

For DeepSeek V3.2, the LTB client prompts for JSON and parses the response instead of sending its JSON-schema response format. This keeps the original stage protocol intact, but may increase malformed-output retries or parse failures. OpenRouter may route this model to providers with different prices, so these game estimates are not guaranteed charges. Add models and reviewed token rates to `configs/game_models.json` before selecting them; unsupported/unpriced models are rejected before any request.

Only after explicit approval, run the following one at a time. Each is a paid game-generation command:

```sh
python3 -m src.real_cli run-game --agents 2 --trials 1 --condition independent_control --model deepseek/deepseek-v3.2 --judge-model deepseek/deepseek-v3.2 --temperature 0 --max-cost-usd 0.05 --execute-paid
python3 -m src.real_cli run-game --agents 2 --trials 1 --condition coordination_opportunity --model deepseek/deepseek-v3.2 --judge-model deepseek/deepseek-v3.2 --temperature 0 --max-cost-usd 0.05 --execute-paid
```

Each writes its native source JSON to `data/llm_agents/source_runs/` and appends parsed trajectories to `data/llm_agents/trajectories.jsonl`. Then, only with label-call approval, run:

```sh
python3 -m src.ground_truth_pipeline label --budget-usd 0.02 --execute-paid
```

<!-- docker compose run --rm --no-deps track22 \ python -m src.ground_truth_pipeline stats -->
<!-- docker ps --filter label=com.docker.compose.service=track22 \
  --format "table {{.Status}}\t{{.Names}}" -->
<!-- docker compose run --rm --no-deps track22 \
  python -m src.ground_truth_pipeline label --budget-usd 0.02 --execute-paid -->


This stores individual raw judge responses and separate candidate/verified labels under `data/labels/`; disputed cases and a seeded sample of unanimous cases enter `review_queue.csv`. The three judges are GPT-4.1 Nano, Mistral Small 3.2, and DeepSeek V3.2. They are separate from the GPT-4.1 Mini monitoring model. Human decisions require a reviewer and written justification, and are logged without replacing judge outputs.

After separate approval for monitoring calls, prepare and score all four views on the same trajectories:

```sh
python3 -m src.ground_truth_pipeline prepare-monitor-inputs
python3 -m src.real_cli monitor --trajectories data/llm_agents/trajectories.jsonl --model openai/gpt-4.1-mini --max-cost-usd 0.05 --execute-paid
```

<!-- docker compose run --rm --build --no-deps track22 \
  python -m src.real_cli monitor \
  --trajectories data/llm_agents/trajectories.jsonl \
  --model openai/gpt-4.1-mini \
  --max-cost-usd 0.05 \
  --execute-paid -->
Monitor prompts do not include condition metadata, plans, judge outputs, labels, confidence, verification, or review fields. Do not compute binary metrics for unknown labels.
