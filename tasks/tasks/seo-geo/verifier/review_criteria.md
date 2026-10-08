# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__evidence_backed_diagnosis` | LLM Judge | Crawler restrictions, SSR and eligibility defects, llms.txt limitations, and confirmed brand-signal counts are reported consistently with the supplied snapshot. |
| `completion__passage_rewrite_quality` | LLM Judge | The report supplies specific rewrites for weak source passages that are self-contained, faithful to the frozen evidence, direct enough to quote, and candid about unsupported claims or missing substantiation. |
| `completion__readiness_scores` | Rule test | The overall, Google AI Overviews, ChatGPT, and Perplexity readiness scores agree with the frozen scoring model and input records. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
