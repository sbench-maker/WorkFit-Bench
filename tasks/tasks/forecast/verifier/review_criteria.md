# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__forecast_math` | LLM Judge | Quota, booked revenue, scoped open pipeline, weighted forecast, gap, coverage, and best/likely/worst amounts follow the frozen data and supplied policies. |
| `completion__stage_rollup` | Rule test | Every in-scope stage reports the correct opportunity count, pipeline value, and stage-weighted value. |
| `completion__commit_upside` | Rule test | All and only in-quarter open opportunities are classified once, policy-qualified deals are committed, and both category totals reconcile to their deal lists. |
| `completion__risk_coverage` | Rule test | The deal-level risk flags cover each policy-defined stale, overdue, compressed-timeline, sponsor, and security issue without leaking closed or out-of-quarter deals into the call. |
| `completion__action_prioritization` | LLM Judge | The output contains a short prioritized action list tied to named financially material or time-sensitive deal risks and the likely quota gap. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
