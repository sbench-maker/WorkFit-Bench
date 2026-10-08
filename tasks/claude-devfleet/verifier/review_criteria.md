# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__mission_plan` | Rule test | The handoff preserves all missions returned by the bundled simulator, their dependency edges, automatic dispatch settings, and actionable mission descriptions. |
| `completion__execution_outcomes` | Rule test | Only the root is manually launched, eligible descendants auto-dispatch, the capacity queue is represented, failed dependencies prevent downstream launch, and every mission reaches its correct terminal state. |
| `completion__report_fidelity` | Rule test | Every terminal mission has one accurate structured report with status, isolated worktree branch where work ran, changed files, test evidence, work summary, errors where applicable, and next steps. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
