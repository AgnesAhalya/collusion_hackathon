# Track 2.2: communication and behavior evidence

This project compares four evidence views on a small, deterministic, scripted public-goods benchmark. It does **not** claim to measure naturally emerging LLM collusion: benchmark labels are controlled scripts. OpenRouter is only used by the evaluation monitor, after explicit user approval. No API request is required for local data generation or tests. Scripted benchmark inputs and outputs are kept under `data/scripted_benchmark/` and `results/scripted_benchmark/`; reserve separate paths such as `data/llm_agents/` and `results/llm_agents/` for future real-agent runs.

See `research_plan.md`, `cleanup_plan.md`, `experiment_notes.md`, and `report_outline.md`. The public-goods payoff implementation is checked against the actual `llm-trust-breaking` function in a host integration test, although the generator remains a deterministic local script. TraceGuard's action-trace consistency is currently only a conceptual adaptation; its evaluator is not invoked.

## Local reproduction

```sh
python -m src.cli make-data
python -m unittest discover -s tests -v
python -m src.cli evaluate --dry-run --smoke
```

For Compose, set `LOCAL_UID` and `LOCAL_GID` to the local account IDs so the non-root container can write only to the project `results/` bind mount. For example, export the values from `id -u` and `id -g` before `docker compose run --rm track22 evaluate --smoke`. The default image user remains non-root. The container has a read-only root filesystem, drops all capabilities, enables `no-new-privileges`, has CPU/memory/process limits, and receives only project data/results mounts; it has no Docker socket or host-network access. OpenRouter requires outbound network access.

Set `OPENROUTER_API_KEY` in the ignored `.env` file and use the fixed monitor identifier to run an approved API evaluation. `OPENROUTER_BUDGET_USD` defaults to 10; each condition uses threshold 0.5. `--dry-run` prints estimated request count and spend; `--smoke` limits the run to one positive and one matched negative trajectory (eight views). Smoke retries are disabled, limiting the run to at most eight HTTP attempts. API requests are cached and responses, usage, and reported or estimated cost are retained. Requests pin the OpenAI provider and disable fallbacks. Figures are dependency-free SVG files. After building the Compose image, run `docker compose run --rm --no-deps track22 evaluate --smoke`. Current price estimate source: [OpenRouter model page](https://openrouter.ai/openai/gpt-4.1-mini); verify it before execution.
