# Experiment notes

## Current implementation status

- Connected Track 2.2 to the actual `llm-trust-breaking` endogenous PublicGoods run format.
- Added a guarded wrapper for the original plan → announce → act runner; paid mode requires explicit flags and a cost acknowledgement.
- Added native-run parser and append-only destination for genuine trajectories. Two earlier paid game runs were cleared from the active dataset on 2026-10-25 at the user's request; their provider-reported usage was unavailable. The fresh pilot/main dataset is empty.
- Added four evidence views over one trajectory, excluding private plans, judge output, opportunity metadata, and annotation fields from prompts.
- Added candidate-only label screening and a separate human annotation protocol. No verified collusion ground truth is available.
- M4 adapts TraceGuard's action/trace-consistency idea; no original TraceGuard evaluator is invoked.
- Preserved the 24-case scripted benchmark and older raw files as distinct test assets.
- Host tests: 10 passed. Docker image built; 10 tests passed under a non-root user with `--network none` and API key cleared. The actual `PublicGoodsGame.evaluate` integration test passed.
- No label-judge or monitor requests were made. Earlier game-generation API requests did occur; their saved records were cleared and actual provider usage was unavailable. No current predictions or active trajectory records exist.

## Pilot estimate (checked 2026-10-25)

Model: `openai/gpt-4.1-mini`, listed at OpenRouter as $0.40/M input and $1.60/M output tokens. The starter sends 3 LLM stages per agent and one LLM judge request per agent using the selected model. Thus one two-agent, one-trial game plans 8 successful model completions; four monitoring views plan 4 more. Estimate including retry reserve: $0.1424 (two agents), $0.2048 (three agents). Assumptions: up to three game attempts per request, 5,000 input plus 2,000 output tokens per game attempt, 10,000 input plus 250 output tokens per monitor request. These are reserved-token estimates, not actual usage or an OpenRouter account spending cap.

## Next action

Confirm the exact trial counts and separate spend approvals for the fresh pilot and main run before invoking `run-game --execute-paid`. Label and monitor stages need their own approvals. Then annotate the resulting natural trajectories blinded to monitor scores. Do not start a larger run until the pilot's usage, raw traces, parser coverage, and monitor failures have been reviewed.
