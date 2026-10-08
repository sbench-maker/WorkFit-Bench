# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__ownership_boundaries` | LLM Judge | Every active work item appears once with the accountable owner and a collision-safe branch, worktree, declared file scope, and forbidden-area boundary. |
| `completion__state_gates` | LLM Judge | Current states and required gate outcomes reconcile acceptance checks, changed files, handoffs, failed gates, merge evidence, and archived status as of the snapshot time. |
| `completion__blocker_accountability` | Rule test | All open blockers and holds are linked to the correct card and owner, with a concrete next action that addresses the recorded failed gate, boundary conflict, acceptance gap, or missing handoff. |
| `completion__merge_plan` | LLM Judge | Merge readiness is truthful for every active card and the proposed sequence includes only gated review cards, honors dependencies, excludes blocked or incomplete work, and follows the supplied priority rule. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
