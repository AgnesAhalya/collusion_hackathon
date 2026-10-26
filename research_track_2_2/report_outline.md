# Report outline (4–8 pages)

1. Abstract: question, controlled design, actual findings after evaluation.
2. Introduction: why communication and behavior may complement one another.
3. Related work: verified references to LLM Trust Breaking and TraceGuard; distinguish their original goals.
4. Research question and hypotheses H1/H2.
5. Experimental environment: original LTB public-goods game and endogenous plan/announce/act protocol.
6. Dataset and labels: genuine model-generated trajectories, candidate evidence, blinded adjudication, and provenance.
7. Monitoring methods: M1–M4; TraceGuard-inspired consistency adaptation with attribution and limitations.
8. Evaluation protocol: fixed model/prompt/temperature/threshold, split, retries, caching, budget.
9. Results: metrics, confusion matrices, failure accounting, costs, per-case comparison; report no results until calls run.
10. Discussion: examples where combined evidence helps/hurts; uncertainty and small-sample limits.
11. Conclusion: evidence-based answer to H1/H2.

## Limitations and Dual-Use / Ethical Considerations appendix

State that an agreement is not itself prohibited by the original game, parser candidates are not verified collusion labels, monitor scores do not prove intent, and public evidence omits private channels. Discuss potential surveillance use, false accusations, data minimization, and human review. Separate starter-derived components from Track 2.2 code.
