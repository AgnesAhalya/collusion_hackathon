# Report outline (4–8 pages)

1. Abstract: question, controlled design, actual findings after evaluation.
2. Introduction: why communication and behavior may complement one another.
3. Related work: verified references to LLM Trust Breaking and TraceGuard; distinguish their original goals.
4. Research question and hypotheses H1/H2.
5. Experimental environment: public-goods game and independent-action rule.
6. Dataset and ground truth: scripted cases, inclusion criteria, provenance, hard negatives.
7. Monitoring methods: M1–M4; exact TraceGuard consistency rubric adaptation.
8. Evaluation protocol: fixed model/prompt/temperature/threshold, split, retries, caching, budget.
9. Results: metrics, confusion matrices, failure accounting, costs, per-case comparison; report no results until calls run.
10. Discussion: examples where combined evidence helps/hurts; uncertainty and small-sample limits.
11. Conclusion: evidence-based answer to H1/H2.

## Limitations and Dual-Use / Ethical Considerations appendix

State that synthetic scripted cases do not establish external validity, monitor scores do not prove intent, and public evidence omits private channels. Discuss potential surveillance use, false accusations, data minimization, and human review. Separate starter-derived components from original benchmark code.
