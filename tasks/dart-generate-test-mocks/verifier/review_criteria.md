# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__runnable_mock_suite` | Rule test | The finished project includes generated Mockito mock source and a test suite that passes against the supplied production code without a live database. |
| `completion__decision_rule_protection` | Rule test | The tests detect regressions in validation, idempotency, stock-state decisions, and the exact-availability boundary documented in the fixture. |
| `completion__database_interaction_protection` | Rule test | The tests detect materially wrong database writes, persisted values, call ordering, audit data, and compensation behavior on asynchronous failures. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
