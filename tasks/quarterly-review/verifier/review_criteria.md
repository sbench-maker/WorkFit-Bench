# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_scope` | LLM Judge | The requested PDF opens as a concise multi-page review and covers revenue, margin, customers, pipeline, opportunities, and risks. |
| `completion__financial_accuracy` | Rule test | Revenue, comparison growth, profit, and margin measures agree with the frozen ledger. |
| `completion__customer_pipeline_accuracy` | Rule test | New wins, churn, concentration exposure, and next-quarter pipeline measures agree with the CRM and ledger exports. |
| `completion__reconciliation_limitations` | Rule test | The PDF reconciles the PayPal channel on the correct basis and makes the CRM sync gap and its decision impact visible. |
| `completion__priorities` | LLM Judge | The PDF identifies next-quarter opportunities and risks, links them to supplied evidence, and states specific owner actions. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
