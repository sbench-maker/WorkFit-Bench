# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__comparative_accuracy` | Rule test | Current and comparison-week product, service, and business values are consistent with the frozen exports, using weighted aggregations and excluding the partial August 31 rows. |
| `completion__alert_grounding` | Rule test | Metrics governed by the supplied alert contract expose the correct threshold severity, owner, channel, and response expectation, with current breaches called out appropriately. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
