# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_scope` | Rule test | output.json is readable, contains exactly one identifiable result for every indexed source file, gives every valid note all requested schema fields, and includes a reviewer summary. |
| `completion__extraction_correctness` | Rule test | Every valid note's extracted values, units, and explicit null reasons agree with the source text and schema, including post-bronchodilator selection, partial dates, redactions, unclear mentions, and omitted fields. |
| `completion__assertion_and_refusal_safety` | Rule test | Negated, possible, historical, hypothetical, patient, and family-member findings retain the correct independent context, and the concatenated two-note source is refused rather than merged. |
| `completion__provenance_validation` | Rule test | Every populated value has a nonempty source location and verbatim evidence present in its own note; the invalid date, out-of-range values, unit mismatch, and unavailable terminology system are surfaced without changing source values. |
| `completion__summary_consistency` | Rule test | Completion, refusal, populated/null, null-reason, and validation totals in the reviewer summary reconcile with the indexed batch and detailed records. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
