# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__runnable_plan_suite` | Rule test | The requested test file is readable, contains Terraform run scenarios, keeps every run in plan mode, and passes against the supplied offline module. |
| `completion__topology_regression_strength` | Rule test | The suite detects material changes to the default subnet count, deterministic CIDR allocation, and round-robin zone placement. |
| `completion__conditional_and_tag_regression_strength` | Rule test | The suite detects endpoint fan-out regressions in both flag states and prevents caller tags from overriding protected module tags. |
| `completion__validation_regression_strength` | Rule test | The suite rejects the unsafe two-subnet production case and detects weakened environment and subnet-count validation boundaries. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
