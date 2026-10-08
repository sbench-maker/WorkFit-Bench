# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_delivery` | Rule test | The revised pricing module and short refactor notes exist at the requested paths, are readable, and the module can be loaded in the supplied project. |
| `completion__quote_behavior` | Rule test | Across the frozen regression matrix, successful return values, exception types and messages, and non-mutation of order inputs remain unchanged. |
| `completion__audit_side_effects` | Rule test | Audit events retain their exact contents and ordering on both successful and rejected orders. |
| `completion__drop_in_contract` | Rule test | The module continues to expose calculate_order_quote and accepts the established order and optional audit_events calling forms. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
