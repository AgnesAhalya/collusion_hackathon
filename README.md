# Apart Research AI Collusion Sprint 2026 — Track 2.2

This workspace is narrowed to Track 2.2 and its direct research dependencies.

- [`research_track_2_2/`](research_track_2_2/) — real-game parser, four evidence views, gated runner, tests, Docker setup, and research protocol.
- [`llm-trust-breaking/`](llm-trust-breaking/) — original public-goods game and endogenous plan/announce/act runner connected by Track 2.2.
- [`trace-guard/`](trace-guard/) — source for the action-trace consistency concept adapted in M4; original evaluator is not invoked.
- [`util/`](util/) — shared model configuration package used by the starter.
- [`literature/`](literature/) — sprint papers and collusion-definition materials.

Static benchmark datasets and the older pilot outputs were removed. Two new game runs and labels are retained; the first monitor attempt is preserved with parser errors pending a fresh run. See [`FLOW_AUDIT.md`](research_track_2_2/FLOW_AUDIT.md) for the checked flow. Track 2.2 runs ask agents for a separate Stage 3 collusion self-report and confidence; judges may see it as evidence, while monitors remain blind to it. Live prompts are in [`prompts/`](research_track_2_2/prompts/README.md). See [`research_track_2_2/README.md`](research_track_2_2/README.md) and its [`labeling_protocol.md`](research_track_2_2/labeling_protocol.md).

The shared configuration template is [`compute.env.example`](compute.env.example). Do not commit a populated `compute.env` or `.env`.
