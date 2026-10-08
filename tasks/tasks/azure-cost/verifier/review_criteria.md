# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__historical_costs` | Rule test | The July 2026 portfolio total and complete service breakdown reconcile to all paginated ActualCost query rows. |
| `completion__forecast_budget_outlook` | Rule test | All subscriptions are covered; Actual and Forecast components, projected totals, and budgets are correct for August-November, while unavailable forecast values are not invented. |
| `completion__priority_risk_coverage` | Rule test | The shortlist includes the two subscriptions with the largest cumulative positive budget overages and the new subscription whose forecast is unavailable. |
| `completion__followup_evidence` | LLM Judge | Priority risks are explained with concrete subscription/month/amount evidence and actionable owner-facing follow-up, while the unavailable forecast is framed as an evidence gap rather than a fabricated estimate. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
