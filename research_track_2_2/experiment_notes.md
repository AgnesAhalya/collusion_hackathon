# Experiment notes

## Current implementation status

- Connected Track 2.2 to the actual `llm-trust-breaking` endogenous PublicGoods run format.
- Added a guarded wrapper for the original plan → announce → act runner; paid mode requires explicit flags and a cost acknowledgement.
- Added native-run parser and append-only destination for genuine trajectories. All previous pilot artifacts have now been removed: native source JSON, parsed trajectories, result bundles/raw-call logs, judge responses, labels, and caches. No experiment trajectories are currently retained.
- Added four evidence views over one trajectory, excluding private plans, judge output, opportunity metadata, and annotation fields from prompts.
- Added candidate-only label screening and a separate human annotation protocol. No verified collusion ground truth is available.
- M4 adapts TraceGuard's action/trace-consistency idea; no original TraceGuard evaluator is invoked.
- Removed the prior static benchmark and legacy `data/raw` datasets. Functional tests now use small in-memory inputs and mocked provider responses.
- Latest host tests: 35 passed, 1 skipped because the host lacks `aiohttp`; Docker tests: all 35 passed under the non-root user with outbound networking disabled. Self-report capture, judge visibility, and monitor blindness are covered. Neither suite made API requests.
- Label-judge requests were previously made; their pilot outputs and caches have been removed. No monitor requests were made. The next dataset must be generated afresh; Stage 3 now asks both conditions for a separate yes/no collusion self-report and confidence. Judges may see that report, while monitors are explicitly blind to it.

## Pilot estimate (checked 2026-10-25)

Model: `openai/gpt-4.1-mini`, listed at OpenRouter as $0.40/M input and $1.60/M output tokens. The starter sends 3 LLM stages per agent and one LLM judge request per agent using the selected model. Thus one two-agent, one-trial game plans 8 successful model completions; four monitoring views plan 4 more. Estimate including retry reserve: $0.1424 (two agents), $0.2048 (three agents). Assumptions: up to three game attempts per request, 5,000 input plus 2,000 output tokens per game attempt, 10,000 input plus 250 output tokens per monitor request. These are reserved-token estimates, not actual usage or an OpenRouter account spending cap.

## Next action

Confirm the exact trial counts and separate spend approvals for the fresh pilot and main run before invoking `run-game --execute-paid`. Label and monitor stages need their own approvals. Then annotate the resulting natural trajectories blinded to monitor scores. Do not start a larger run until the pilot's usage, raw traces, parser coverage, and monitor failures have been reviewed.
