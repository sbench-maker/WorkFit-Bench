# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__endpoint_assessment` | Rule test | All supplied candidate endpoints are covered with data-consistent scores and classes, EP-01 is the sole primary recommendation, and the unvalidated EP-03 surrogate is visibly kept from primary use. |
| `completion__sample_size_estimate` | Rule test | The planning packet reports the correct two-arm proportions estimate under the supplied response rates, alpha, power, and dropout assumptions, including the correct total requirement. |
| `completion__feasibility_pressure_test` | Rule test | The phase-gate result and its component scores agree with the current plan, while selected-site coverage and bottom-up CRM enrollment are aggregated correctly. |
| `completion__conditional_decision_quality` | LLM Judge | The recommendation states a conditional gate addressing the statistical shortfall, CRM enrollment gap, operational burden, and budget gap; it does not treat an automated score as authorization. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
