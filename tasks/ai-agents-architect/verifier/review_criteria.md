# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The requested project copy and full-suite evaluation exist, compile, and run through the documented offline entry point. |
| `completion__orchestration_outcomes` | Rule test | Every frozen incident is handled once, valid evidence paths reach the correct verified remediation, and designated uncertainty or failure paths escalate with a reason. |
| `completion__bounded_safety` | Rule test | Retries, repeated calls, and role/tool budgets remain bounded; production P1 mutations follow oversight; failed or uncertain investigations never claim unsafe success. |
| `completion__state_consistency` | Rule test | Ordered traces expose role decisions and failures, aggregate counts reconcile with runs, and memory stores one compact reusable record per resolved signature without raw execution content. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
