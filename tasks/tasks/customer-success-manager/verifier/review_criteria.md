# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__scoring_rollups` | Rule test | The scored population, health distribution and average, churn distribution and ARR exposure, and modeled versus eligible expansion totals agree with the frozen CRM data and operating policy. |
| `completion__queue_decisions` | Rule test | The save queue includes every account triggered by health, churn tier, or a critical warning in the declared priority order; the growth queue contains only healthy, low-risk accounts without severe warnings, is correctly ranked, and reports correct opportunity value. |
| `completion__data_quality_quarantine` | Rule test | Every incomplete or contradictory account is excluded from scoring and action queues and appears once in human review with the actual defect identified. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
