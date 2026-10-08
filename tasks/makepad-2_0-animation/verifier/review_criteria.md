# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__hover_behavior` | Rule test | StatusCard owns a supported Animator, drives a per-instance hover value through the requested off/on transition, interpolates the supplied colors, uses the requested timing/ease/cursor, and keeps its label above the background. |
| `completion__spinner_behavior` | Rule test | SyncSpinner starts its time track on, loops at the requested duration, and animates a per-instance rotation through a full turn that the arc shader consumes. |
| `completion__integration_contract` | Rule test | The panel retains its widget names, IDs, dimensions, spacing, copy, colors, and spinner geometry; hover and time remain independent, and no Animator is attached to an unsupported widget definition. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
