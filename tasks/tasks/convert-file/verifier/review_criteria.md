# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__record_fidelity` | Rule test | Every source event appears exactly once and all values, including nulls, empty text, Unicode, timestamps, decimals, booleans, and large integers, retain their meaning. |
| `completion__schema_preservation` | Rule test | All source columns, and no invented columns, are present with compatible logical field types for downstream use. |
| `completion__month_partitioning` | Rule test | The dataset is physically partitioned by campaign_month, covers all source months, and places no row in the wrong month partition. |
| `completion__zstd_compression` | Rule test | Every populated Parquet column chunk uses Zstandard compression. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
