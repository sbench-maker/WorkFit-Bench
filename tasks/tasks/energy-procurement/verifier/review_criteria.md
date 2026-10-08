# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__load_profile_accuracy` | Rule test | Every facility is profiled once with annualized MWh, interval peak kW, and load factor correctly derived from the representative interval records and day weights. |
| `completion__offer_screening_and_costing` | Rule test | All and only policy-eligible offers are compared, and each offer's base, high, and low total delivered costs correctly combine profiled load, scenario-index terms, price bounds, supplier charges, and site network costs. |
| `completion__award_compliance_and_budget_consistency` | Rule test | The recommended market allocations use eligible offers, satisfy share, diversification, concentration, and hedge limits, and their scenario costs and budget variances reconcile to the component offers. |
| `completion__portfolio_decision_rationale` | LLM Judge | The award and hedge recommendation compares base cost, stress exposure, concentration, and counterparty risk against a cheaper or safer alternative and states the decision trade-off. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
