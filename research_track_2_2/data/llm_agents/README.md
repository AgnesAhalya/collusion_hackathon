# Genuine LLM trajectory files

The guarded `src.real_cli run-game` command writes native starter-run JSON under `source_runs/` and appends parsed trajectories to `trajectories.jsonl`. `prepared_monitor_views.jsonl` is generated offline. No native runs or parsed trajectories are currently retained; prior pilot data was removed. New Track 2.2 games include a Stage 3 agent self-report, recorded separately from actions and available to the labeling judges. Monitor views must omit it.
