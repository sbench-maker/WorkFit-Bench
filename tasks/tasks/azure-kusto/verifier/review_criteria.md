# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__incident_identification` | Rule test | The report selects the correct service and region and identifies the complete sustained dual-objective breach window through recovery. |
| `completion__metric_correctness` | Rule test | Request volume, error rate, p95 latency, and the equal-length pre-incident baseline agree with the supplied data. |
| `completion__correlation_correctness` | Rule test | The reported deployment ID and version reconcile with deployment metadata, and the top endpoint reflects incident failures. |
| `completion__kql_reproducibility` | LLM Judge | The included KQL is syntactically plausible against the supplied ADX schemas and can reproduce hourly dual-objective detection plus deployment and endpoint correlation without silently widening the incident window. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
