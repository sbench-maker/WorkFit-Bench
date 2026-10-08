# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The requested router and JSON result exist, the result can be normalized as routing decisions, and the router exposes the documented command-line interface. |
| `completion__primary_coverage` | Rule test | Every primary ticket is represented exactly once and no unrelated ticket is added. |
| `completion__routing_correctness` | Rule test | Ordinary tickets receive the rule, category, priority, team, review flag, and action dictated by the first matching policy rule or fallback. |
| `completion__precedence_and_safety` | Rule test | Mixed-signal escalations obey rule precedence, privacy/access verification stays human-reviewed, Unicode text is handled, and unmatched feedback uses fallback. |
| `completion__summary_consistency` | Rule test | Processed, category, priority, and human-review totals reconcile with the submitted decisions. |
| `completion__constrained_batch_runtime` | Rule test | The router reruns on the supplied alternate batch through schema-constrained batch generation and records substantial shared-prefix reuse with no schema failures. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
