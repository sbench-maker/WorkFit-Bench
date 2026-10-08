# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__runnable_suite` | Rule test | The completed repository is present, retains the supplied production source, and its test suite compiles, discovers tests, and passes against the supplied implementation offline. |
| `completion__validation_contract` | Rule test | The suite detects regressions that admit quantity 51, whitespace-only SKUs, or empty line collections instead of rejecting them before gateway work. |
| `completion__inventory_decisions` | Rule test | The suite protects inclusive stock equality, case-insensitive and whitespace-normalized SKU grouping, and summed duplicate quantities. |
| `completion__commit_and_result` | Rule test | The suite detects a missing commit, an untrimmed request ID sent to the gateway, and a TotalUnits value based on distinct SKUs rather than submitted quantities. |
| `completion__cancellation` | Rule test | The suite protects pre-cancelled short-circuiting and propagation of the original token to both availability lookup and commit. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
