# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_offline_usability` | Rule test | The requested HTML exists, is readable as a substantive dashboard, and has no remote resource dependency that would break offline use. |
| `completion__headline_kpi_correctness` | Rule test | Current MRR, growth, churn, CAC, LTV/CAC, and the month-over-month MRR bridge agree with the supplied subscription and acquisition data. |
| `completion__trend_and_drilldown_coverage` | Rule test | The dashboard provides accurate multi-month MRR context and a correct causal churn breakdown by a useful dimension such as reason or segment. |
| `completion__alert_decision_consistency` | Rule test | The active alert set includes every enabled breached target and excludes healthy or explicitly non-alerting metrics. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
