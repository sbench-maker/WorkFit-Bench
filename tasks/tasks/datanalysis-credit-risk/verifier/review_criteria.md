# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__sample_quality` | LLM Judge | The report reconciles cleaning counts, OOS separation, abnormal-month decisions, and organization/month quality coverage from the frozen applications extract. |
| `completion__feature_evidence` | Rule test | Missingness, IV, PSI, null-importance, and material correlation evidence agrees with the screening base and frozen diagnostic exports, including strict-threshold boundaries. |
| `completion__screening_decisions` | Rule test | Each material rejection is assigned to the correct first failing gate and the final retained-variable set follows the policy order and correlation protection rule. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
