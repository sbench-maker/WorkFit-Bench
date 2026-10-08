# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__scope_disposition` | Rule test | The plan moves the navigation/process and native-window cases to browser coverage while retaining the empty-URL guard and URL formatting cases as unit tests. |
| `completion__behavior_evidence` | LLM Judge | The plan accurately traces the migrated assertions through the supplied production code and existing browser-test precedents, distinguishing real navigation, process readiness, native initialization, registration, visibility, and close notification from test-only shortcuts. |
| `completion__implementation_build_plan` | LLM Judge | The handoff proposes coherent browser fixtures, preserves the remaining unit file where needed, identifies source-list and ChromeOS-conditional build changes, and avoids unnecessary production edits. |
| `completion__lifecycle_safety` | LLM Judge | The plan prevents process-readiness, partial AppWindow initialization, and observer-order teardown failures with concrete setup, waits, and native close ordering grounded in the checkout. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
