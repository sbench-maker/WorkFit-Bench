# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_viability` | Rule test | The requested index.html exists, is readable as a substantial single-page document, contains an interactive control, and does not depend on remote assets. |
| `completion__evidence_fidelity` | LLM Judge | The dashboard traces claims to a representative mix of supplied interviews, usability observations, tickets, surveys, analytics, sales notes, and stakeholder context while preserving decision-critical quotes and metrics. |
| `completion__decision_scope` | LLM Judge | The artifact covers evidence, themes, the three named alternatives, a recommendation, a concise decision memo, experiments, and limitations. |
| `completion__internal_consistency` | Rule test | The recommendation remains identifiable across the artifact, experiments contain concrete measurable thresholds, and any numeric opportunity totals reconcile with their component scores. |
| `completion__decision_judgment` | LLM Judge | The recommended September move reasonably weighs cross-source evidence, account-size differences, sprint constraints, and uncertainty; it states what could change the decision and proposes a reversible learning step. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
