# Apart Research AI Collusion Sprint 2026 — Track 2.2

This workspace is narrowed to the Track 2.2 experiment and its direct research dependencies.

- [`research_track_2_2/`](research_track_2_2/) — benchmark, monitoring pipeline, Docker setup, and research notes.
- [`llm-trust-breaking/`](llm-trust-breaking/) — public-goods game and candidate source for future real-agent trajectories.
- [`trace-guard/`](trace-guard/) — action-trace monitoring source being evaluated for an adapted integration.
- [`util/`](util/) — shared `poseidon_compute` package required by the starter projects' model configuration.
- [`literature/`](literature/) — sprint papers and collusion-definition materials relevant to research design.

The Track 2.2 pipeline's runtime path uses the Python standard library and Docker Desktop. The scripted benchmark does not call an agent-generation model. OpenRouter monitoring is a separate paid step and requires a key in `research_track_2_2/.env`.

For local reproduction, see [`research_track_2_2/README.md`](research_track_2_2/README.md). The shared compute configuration template is [`compute.env.example`](compute.env.example); never commit a populated `compute.env`.
