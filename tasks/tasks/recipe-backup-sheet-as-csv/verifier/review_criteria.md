# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__csv_usability` | Rule test | The requested file exists and is a non-empty, rectangular UTF-8 CSV that standard CSV readers can parse. |
| `completion__header_fidelity` | Rule test | The CSV preserves the active Recipe Catalog sheet's header labels and column order. |
| `completion__record_scope` | Rule test | All and only Recipe Catalog records appear once, in the same row order, with no archive or reference-tab substitution. |
| `completion__cell_fidelity` | Rule test | Every non-key cell preserves the source value, including empty cells, punctuation, Unicode, commas, quotes, and embedded newlines. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
