# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__unit_dispositions` | Rule test | Every work item appears once and is preserved, resumed, scoped for replay, isolated, escalated, or dependency-held according to current evidence and policy. |
| `completion__restart_plan` | Rule test | Only eligible units are scheduled, every dependency precedes its consumer, applicable gates are rerun, and estimated cost reconciles within the restart reserve. |
| `completion__recovery_controls` | Rule test | The runner receives correct retry and repeat limits, hard-stop gates, per-unit allowances, and a snapshot-bound frozen checkpoint that preserves completed work. |
| `completion__loop_control` | Rule test | The plan selects the loop mode implied by the campaign signals and freezes the stalled, repeatedly failing campaign. |
| `completion__evidence_handoff` | LLM Judge | Non-routine recovery actions are explained with concise, traceable run evidence, and each release-lead review identifies the decision, affected dependency chain, and safe next step. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
