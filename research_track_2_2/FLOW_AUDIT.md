# Track 2.2 flow audit — 2026-10-26

The code path was traced from CLI arguments to saved statistics. No model API calls were made for this audit. The pilot runs and their derived files were subsequently removed at the user's request on 2026-10-26.

| Step | Path checked | Result |
| --- | --- | --- |
| 1. Preflight and paid gate | `src/real_cli.py`, `src/real_runner.py` | Paid game execution requires `--execute-paid` and an estimate at or below `--max-cost-usd`. The estimate is a local reserve, not a provider spending limit. |
| 2. Conditions | `run_endogenous.py`, `trial_runner.py` | Both study arms have the same independent-decision instruction and simultaneous announcements. Control hides peers' announcements at the final choice; opportunity shows them. |
| 3. Game prompts | `prompts/game_*.txt`, `prompt_builders.py` | Actual study prompts are loaded from individual files. Stage 1 now describes the correct visibility for each condition. |
| 4. Game responses | `parallel_openrouter_async.py`, `trial_runner.py` | Raw attempts are recorded without authorization headers. Direct parsed responses retain the self-report fields. Final actions reject malformed numeric values. |
| 5. Native run and parsing | `run_endogenous.py`, `src/real_trajectories.py` | The original game computes outcomes. One trajectory is parsed per trial, including private plans, announcements, actions, action reasoning, outcomes, and self-reports. |
| 6. Readable results | `src/real_runner.py` | A timestamped bundle includes native source JSON, trajectories, readable summary, and raw call usage. Completeness checks include required self-reports and final-action reasoning. |
| 7. Judge packet | `src/ground_truth_pipeline.py`, `src/label_verification.py` | Condition metadata is omitted. Judges see the agent self-reports and final-action reasoning as claims; both are citeable. |
| 8. Three judges | `src/collusion_judges.py`, `src/judge_prompts.py` | Three configured model families vote independently. Each request is cached by model, full prompt, system prompt, schema, and version. The spend cap applies to new requests in that invocation. |
| 9. Verification and voting | `src/judge_aggregation.py`, `src/label_verification.py` | Majority, confidence, cited evidence, action agreement, protocol, and self-report completeness are checked before an automatic label. Invalid judge responses do not contribute evidence. Unknown remains available. |
| 10. Human queue | `src/label_review.py` | Queue and packets append new cases without overwriting prior rows or human reviews. An incomplete queue pair blocks paid labeling before calls. |
| 11. Monitors and stats | `src/evidence_views.py`, `src/real_cli.py`, `src/ground_truth_pipeline.py` | M1–M4 project only their allowed evidence. Self-reports, private plans, labels, and judge decisions are excluded. Stats distinguish historical saved labels from labels usable under the current prompt and verifier. |

## Current data state

No native runs, raw calls, trajectories, label outputs, judge cache, review queue, or monitor outputs are retained. The empty Docker mount directories remain ready for a fresh run.

## Verification

The host suite passed 38 tests with one Docker-only test skipped. The rebuilt Docker container passed all 38 tests. Tests use mocked provider responses and made no model API calls. A fresh paid game and label run has not been executed under the new prompts; the actual model behavior and provider charges remain unverified.
