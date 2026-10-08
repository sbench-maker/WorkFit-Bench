# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__change_feed_coverage` | Rule test | The requested JSON and runnable project exist, and the feed covers every newly added or materially updated eligible model without duplicate or unusable records. |
| `completion__collection_normalization` | Rule test | Emitted records reflect the authoritative latest crawl cards, use canonical URLs, preserve the model facts, and exclude entries that fail the configured eligibility rules. |
| `completion__enrichment_correctness` | LLM Judge | Every required change has the correct compatibility score and priority after applying the supplied bands, thresholds, and learned positive or negative feedback signals. |
| `completion__persistence_consistency` | Rule test | The local persisted state retains prior records, inserts new eligible models, updates material changes, and does not create duplicate canonical identities. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
