# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_scope` | Rule test | The Markdown artifact is readable, compact enough for an owner check-in, and includes overall health, finance, sales, pipeline, commitments, a single priority, and source availability. |
| `completion__metrics_and_period_changes` | Rule test | Cash, revenue, AR aging, payment settlements, weighted pipeline, target coverage, closed-won activity, new deals, and their relevant comparisons reconcile to the frozen exports. |
| `completion__material_risk_coverage` | Rule test | Every record meeting the owner's configured overdue-invoice, failed/pending-payment, stale-deal, or slipped-deal settings is named with its amount and attention reason. |
| `completion__source_honesty_and_signal_filtering` | Rule test | Available and unavailable connector states are represented accurately, Gmail is not presented as pulled, and obvious routine internal noise is not promoted as an urgent customer risk. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
