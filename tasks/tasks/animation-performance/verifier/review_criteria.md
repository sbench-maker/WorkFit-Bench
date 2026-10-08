# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__deliverable_integrity` | Rule test | The requested unified patch applies cleanly to the supplied checkout and the review is present, readable, and substantive enough to hand off. |
| `completion__compositor_optimization` | Rule test | The patched motion no longer transitions layout-triggering properties or uses them in keyframes, while the fixture's existing transform/opacity effects remain functional. |
| `completion__state_fidelity` | Rule test | Drawer, dialog, toast, progress, and status-badge endpoints remain consistent with the supplied desktop and compact state notes, including the toast's combined scale cue. |
| `completion__reduced_motion` | Rule test | Reduced-motion mode suppresses nonessential motion across the gallery without changing the legible interaction endpoints. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
