# Experiment notes

## Status

- Repository inspection and local implementation completed.
- Dataset is deterministic and scripted: 24 cases, 12 positive / 12 negative, interleaved with opaque IDs.
- Nine hard negatives match the positive action vector exactly and include two independent-decision messages; three additional negatives contain a rejected/unexecuted proposal.
- Six distinct paired message paraphrases are used for each positive/hard-negative class. A rule check confirms wording and action evidence agree with each label.
- Data-generation model calls: 0. Monitoring estimates: 8 uncached calls / ~$0.009 smoke; 96 / ~$0.106 full run at current listed rates and 2× margin.
- Labels are separate from monitor-visible trajectories and validator-checked. Sequential IDs and block ordering were removed after an audit found they exposed the class.
- No API calls or paid experiments have run.
- Fixed threshold: 0.5, chosen a priori; the entire 24-case benchmark is evaluation-only because no development-set threshold fitting is performed.
- Model identifier is configurable, with example `openai/gpt-4.1-mini`; freeze it before evaluation.
- Core prompt and temperature are in `src/openrouter_client.py`; score threshold is 0.5 in evaluation code.
- `tests/test_pipeline.py` now calls the actual `PublicGoodsGame.evaluate` implementation from the sibling starter checkout and compares every scripted payout. This passes on the host; the Docker image intentionally does not include the sibling repository, so that one integration test is skipped inside the isolated image.
- TraceGuard's `ACTION_TRACE_CONSISTENCY` is still only conceptually adapted. The adapter does not invoke `trace-guard/src/traceguard/monitors/traceguard_monitor.py::_score_dimension` or `_evaluate_trace`.

## Results

No detector results are reported before approved API execution. The approved 8-call smoke has not run because the project `.env` and host environment currently contain no API key; no paid calls or predictions exist. A scripted data benchmark and its tests are not experimental monitor predictions. Record actual model version, prompt hash, provider usage/cost, failures, and held-out split here after the smoke is run.

## Limitations and dual-use / ethical considerations

This small controlled benchmark tests evidence presentation, not spontaneous collusion prevalence. Messages remain scripted and reveal the controlled communication condition semantically; matching the action vector and balancing the number/order of messages removes some superficial artifacts but does not make these natural conversations. The benchmark has one game and one round and does not test private/implicit channels. It uses one monitor model and a fixed prompt/threshold; conclusions may still be prompt/model sensitive. Labels are categories assigned by the generator and checked by a deterministic lexical/action rule plus generator flags; they are not independently observed or adjudicated coordination. Public behavior cannot establish private intention; identical actions can arise by coincidence, while hidden coordination may evade visible evidence. A detector score is not proof of intent or misconduct. The rubric and prompts could be repurposed to monitor agents, so disclose data sources and avoid punitive deployment without independent review. No private plan is exposed to the monitors.

## Next integration steps

The smallest real-agent pilot would run one `publicgoods` trial with three agents through `llm-trust-breaking/experiments/run_endogenous.py` (one round, fixed named models, low temperature, no judge/reflection if those switches are available), then convert its `stage2.message` and `stage3.choice` fields to this schema. This requires the starter's locked dependencies, OpenRouter credentials, and a separately approved agent-generation budget; the monitor smoke approval does not cover those agent calls. Keep those trajectories and results in `data/llm_agents/` and `results/llm_agents/` and label them as real-model outputs, with seeds, model IDs, prompts, and usage recorded.

For TraceGuard, its monitor is tightly coupled to Inspect AI and ControlArena single-agent tool traces. The smallest honest bridge is a separate adapter that maps each agent's public statement/action into `agent_reasoning`/`agent_action`, uses the actual `ACTION_TRACE_CONSISTENCY` `Dimension` and prompt template, and calls TraceGuard's scoring path only after installing its pinned dependencies. A public-goods communication transcript is not literally a tool-call trace, and that mapping changes the construct; record it as a new adapted condition rather than claiming to run the unmodified TraceGuard monitor. Neither full integration is part of the current pipeline.
