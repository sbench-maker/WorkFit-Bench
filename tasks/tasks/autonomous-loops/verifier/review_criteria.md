# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__dag_safety` | Rule test | Every RFC work unit is represented once; parallel waves respect dependencies, agent capacity, and shared-file exclusions; isolated ownership boundaries and integration order are safe. |
| `completion__risk_adaptation` | Rule test | Each unit receives the policy tier and ordered quality stages appropriate to its complexity, while large, critical, and irreversible changes receive the required human approvals at the correct control point. |
| `completion__bounded_recovery` | Rule test | The plan persists the required run and unit state and gives each listed failure a bounded action, evidence capture set, retry limit, and resume point, including non-retryable exhaustion events. |
| `completion__termination_and_merge_controls` | Rule test | Merge eligibility uses all required evidence, and success, consecutive completion signaling, cost, duration, pass, run-count, and operator-abort conditions prevent premature completion or unbounded execution. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
