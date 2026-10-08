# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The requested JSON exists, parses, and exposes the three comparison groups, per-status severity totals, and a release-gate decision. |
| `completion__comparison_and_deduplication` | Rule test | Every canonical finding is classified exactly once as new, fixed, or unchanged after applying the supplied identity and deduplication policy. |
| `completion__finding_fidelity` | Rule test | Reported findings retain the correct rule, effective severity, source message, normalized repository-relative file, and start line. |
| `completion__summaries_and_gate` | Rule test | Per-status severity totals reconcile to the canonical finding groups and the gate follows the manifest rule for new error-level findings. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
