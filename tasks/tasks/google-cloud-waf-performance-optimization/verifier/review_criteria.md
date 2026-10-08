# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__requirement_outcomes` | Rule test | Every requirement breached by the frozen load-test results is identified, while requirements that meet their target are not misclassified as breaches. |
| `completion__quantitative_evidence` | Rule test | Breach decisions include their measured values, and the checkout/database, inventory-worker, and catalog bottlenecks are tied to the decisive telemetry in the supplied files. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
