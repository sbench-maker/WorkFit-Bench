# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The requested JSON is readable and contains a recognizable planning record for every supplied SKU. |
| `completion__forecast_correctness` | Rule test | Four-week SKU forecasts follow the supplied policy for stable, trending, seasonal, and intermittent demand while excluding promotional and stockout-censored observations. |
| `completion__safety_stock_correctness` | Rule test | Safety stock is recalculated by SKU from eligible demand variability, target service level, and both average and variable new lead time. |
| `completion__replenishment_correctness` | Rule test | Inventory position correctly includes eligible open POs, commitments, and backorders, and recommended orders satisfy target stock, case-pack, MOQ, and zero-need rules. |
| `completion__risk_flag_correctness` | Rule test | The deliverable identifies exactly the SKUs projected to stock out before replenishment can arrive, accounting for qualifying PO arrivals. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
