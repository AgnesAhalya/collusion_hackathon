# Workspace scope

The workspace is narrowed to the Track 2.2 experiment and the components it uses or directly evaluates.

## Retained

- `research_track_2_2/` — real-game integration, parser, four-view monitor pipeline, functional offline tests, and research documentation. No static benchmark datasets are retained.
- `llm-trust-breaking/` — public-goods implementation and planned real-agent trajectory source.
- `trace-guard/` — source for the monitoring dimension and possible adapted scoring integration.
- `util/` — shared model configuration package used by the starter projects.
- `literature/` — sprint papers and definitions relevant to the research question.
- Root Git metadata, `.gitignore`, `README.md`, `COMPUTE.md`, `compute.env.example`, and `setup.sh` — version history, workspace orientation, shared setup, and configuration template.

## Removed from the workspace

Independent sprint projects unrelated to Track 2.2 were removed: `algorithmic-pricing-llms/`, `collusive-llm-agents/`, `colosseum/`, `focal-points/`, `llm-agent-collusion/`, `llm-agent-collusion-2/`, `llm-cartel/`, `redteaming/`, and `steganographic-collusion/`.

The Track 2.2 data and results directories and both starter projects were preserved. No credentials were present in the removed project roots.
