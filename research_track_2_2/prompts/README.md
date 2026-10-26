# Prompts used by Track 2.2

Each `.txt` file is loaded by the live pipeline. Game prompts use `$name` placeholders filled from the current trial. The source game rules and agent messages are inserted at runtime. These files are the editable source for future runs; saved `raw_calls/calls.jsonl` records the exact rendered prompts sent in completed game runs.

- `game_stage1_*`, `game_stage2_*`, `game_stage3_*`: agent system and user prompts.
- `game_json_*`: extra format instructions for models without structured output.
- `game_independent_rule.txt`: study instruction shared by both conditions.
- `native_judge_system.txt`: the original game consistency judge.
- `label_judge_*`: the three independent collusion judges.
- `monitor_system.txt`: all four monitor views.

Changing a prompt creates a new experimental protocol. Record the prompt files' hashes with each run and do not pool runs under different prompt versions without accounting for that change.
