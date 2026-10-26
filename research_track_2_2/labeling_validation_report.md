# Labeling pipeline validation report

Status: all pilot game runs and derived results were removed on 2026-10-26 at the user's request. See `FLOW_AUDIT.md` for the current code audit. No model API calls were made during the audit or cleanup.

## Implemented

* Track 2.2 experimental intervention wired into the existing LTB `run_endogenous.py` path. Both arms get the same documented independent-decision instruction. Independent control withholds peer Stage 2 announcements from each Stage 3 prompt; coordination-opportunity retains peer visibility. Stage 2 is simultaneous in both. `PublicGoodsGame.evaluate` and payoff code are unchanged.
* The canonical trajectory parser now records arm assignment, visibility, and per-agent parse status, and does not infer label candidates from lexical templates. Parsed cases stay `unlabeled` until the separate panel/verification process.
* Three-model OpenRouter judge panel, frozen model config and prompt hash, local JSON validation, two-attempt ceiling, cache and local spend cap, majority/confidence aggregation, event-quote verification, human review queue, append-only review decisions, and monitor-input leakage checks.
* The label panel is separate from the GPT-4.1 Mini monitors and does not reuse their predictions. Monitor inputs are written to a separate directory and omit private plans, treatment fields, label fields, judge outputs, verification and review data.

## Offline tests

The current host suite passes **38 tests** with one raw-call-capture test skipped because `aiohttp` is not installed on the host. The rebuilt Docker suite passes **38 tests**. Tests cover DeepSeek-specific pricing, game-judge model selection, starter filename recovery, raw usage aggregation, label acceptance and review, all three study game prompts, parser, monitoring, caching, and evaluation checks. No model API requests were made by tests.

The final rebuilt Docker suite passed all **38 tests**, including the raw API-call capture test. The service uses a non-root UID/GID, read-only root filesystem, dropped capabilities, no-new-privileges, CPU/memory/PID limits, tmpfs `/tmp`, and read-only source/starter mounts. Tests mock model responses and made no model API requests.

The test cases use in-memory trajectories and mocked responses; they include unanimous and 2/3 votes, unknown ties, low confidence, nonexistent quotes, proposed-but-unexecuted agreements, same-action independent controls, missing actions, malformed JSON, explicit contradiction, human override provenance, private-plan isolation, monitor label leakage, cache hits, raw-usage aggregation, and a paid-call guard. The integration test calls the starter's real `build_stage3_prompt` and checks peer-message visibility in each arm. No static benchmark datasets are retained.

## Pilot reservation

Game-agent and original game-judge models are independently selectable from `configs/game_models.json` and via `--model` / `--judge-model`. With both set to DeepSeek V3.2, one independent-control game is estimated at **$0.0399** (8 logical requests, up to 24 attempts). Keeping the default GPT-5 Mini game judge yields **$0.0614**. For two agents and one trial in each condition, using DeepSeek for both agent stages and the native game judge: 12 game-agent calls, 4 native game-judge calls, 6 independent labeling-judge calls, and 8 monitor calls. The estimate is **$0.0798** for game generation and its native judge, **$0.0102** for labeling, and **$0.0352** for monitors, for **$0.1253** total (rounded from unrounded components). A 25% operational margin gives about **$0.16**. Keeping the game judge at GPT-5 Mini raises the full-pilot estimate to **$0.1683** (about **$0.21** with margin). Local reserve checks are not provider-enforced limits. OpenRouter may route requests among providers, so actual pricing can differ.

The 20–40 trajectory goal is cost-feasible at the same conservative assumptions and a matched two-condition design, with DeepSeek for both game agents and the native game judge: 20 trajectories about $1.25 base / $1.57 with 25% margin; 40 about $2.50 base / $3.13 with margin. That is only a cost projection, not a quality guarantee; actual positives may be rare, cases may remain unknown, and no class balance will be forced.

## Remaining limits

1. No trajectories or labels are currently retained. A fresh run under the corrected parser and prompts is needed for current-protocol labeling. New runs capture raw API usage, and the Stage 3 self-report is a behavioral intervention applied equally in both conditions.
2. Judges do not receive the arm identifier. This protects against direct label leakage, but means they cannot use control assignment to label negatives. The deterministic verifier uses hidden run metadata only after judgments. Some true independent-control cases may therefore remain unknown.
3. Natural-language agreement and whether it violated the study instruction cannot be fully proven by deterministic code. Exact quotes, participant IDs, parse flags, and action execution can be machine-checked; reviewers must assess the semantics.
4. The original game has an internal GPT-5 Mini judge call per agent. That is additional to the three stage calls and is included in the cost estimate; its labels are not used as study labels.
5. Game API execution has no provider-enforced maximum spend. The code checks local estimates before launch and monitors its own panel budget, but provider pricing/tokenization/retries can differ. Use an account-level provider budget and stop if the estimate changes.
6. OpenRouter model aliases are frozen in config but aliases/prices can change. Recheck the exact IDs and rates before the pilot; do not treat the current model pages as a future price lock.

## Exact approval commands

Offline preflight and test commands are in `README.md`. For the two-arm pilot, each game run must be separately authorized; with DeepSeek for agents and the native game judge, the planned game-only local cap is $0.05 per arm. After both generate and parse trajectories, label judges use a $0.02 local cap for new requests in that invocation; monitors use a separate $0.05 cap. These are local safeguards and not vendor-side hard limits. Monitoring calls should remain separately approved, as specified by the study owner.

Current rates checked 2026-10-25 against OpenRouter listings: GPT-4.1 Nano $0.10/$0.40 per million input/output tokens, Mistral Small 3.2 24B $0.075/$0.20, DeepSeek V3.2 $0.2088/$0.3096, and GPT-5 Mini $0.25/$2.00: [GPT-4.1 Nano](https://openrouter.ai/openai/gpt-4.1-nano/providers), [Mistral Small 3.2 24B](https://openrouter.ai/mistralai/mistral-small-3.2-24b-instruct/providers), [DeepSeek V3.2](https://openrouter.ai/deepseek/deepseek-v3.2), [GPT-5 Mini](https://openrouter.ai/openai/gpt-5-mini/providers). Game models and rates are configured in `configs/game_models.json` and selected independently. The LTB client does not include DeepSeek V3.2 in its JSON-schema capability table, so it asks the model for JSON in the prompt and parses the response; malformed stage or judge output may increase retries or parse-failure risk.

## Updated execution plan

1. Offline implementation and regression suite: host suite 37 passed, 1 skipped because `aiohttp` is Docker-only.
2. Docker regression suite: 38 tests passed.
3. Current-protocol pilot artifacts: pending. Generate new runs under the corrected parser and prompt files before current-protocol labeling or monitoring.
4. Main run and label panel: pending fresh pilot review and separate trial-count/spend approval. The judges may see self-reports but must validate claims against recorded messages/actions.
5. Monitoring: pending separate call approval. Monitors must remain blind to self-reports, labels, plans, and condition metadata.
