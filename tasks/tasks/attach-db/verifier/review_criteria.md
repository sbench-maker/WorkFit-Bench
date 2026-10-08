# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__shared_state_preservation` | Rule test | The staged init file retains the UTC setting, safe_ratio macro, and existing read-only historical attachment under its original alias. |
| `completion__attachment_semantics` | Rule test | The init state attaches the intended snapshot exactly once as support_ops_snapshot, selects it for unqualified queries, and declares the attachment read-only. |
| `completion__report_identity_scope` | Rule test | The report identifies the resolved snapshot and chosen alias and covers every physical table, including the empty import_rejects table, with no invented tables. |
| `completion__schema_details` | Rule test | Reported row counts and ordered column name/type definitions match the attached DuckDB snapshot for every table. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
