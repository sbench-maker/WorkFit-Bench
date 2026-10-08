# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__feature_coverage` | LLM Judge | The combined plan and checklist cover the frozen specification's material persistence, API, content, scheduling, recipient, delivery, audit, UI, migration, and flag-enforcement obligations without depending on exact headings or ordering. |
| `completion__sequencing_and_slicing` | LLM Judge | Tasks follow credible technical dependencies, expose safe parallel work, deliver coherent vertical slices where practical, and keep the system reviewable at intermediate states. |
| `completion__risk_and_review_controls` | LLM Judge | The plan makes the DST, activity-visibility, and failure-alert decisions explicit; assigns sensible decision gates; respects non-goals; and places human checkpoints before schema commitment, live delivery, and staged rollout with rollback and monitoring evidence. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
