# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The requested manifest and referenced non-empty weights artifact are readable and identify the supplied checkpoint. |
| `completion__deployment_configuration` | Rule test | The package uses calibration-free HQQ on the requested axis, selects the preferred optimized T4 backend, covers every layer, preserves the vocabulary endpoints, and uses only permitted precisions and group sizes. |
| `completion__quantized_payload_integrity` | Rule test | Every source row is represented exactly once; protected weights remain intact; and all HQQ groups, codes, scales, zero points, including partial tail groups, are the deterministic result of the selected configuration. |
| `completion__quality_and_optimality` | Rule test | Reconstruction from the submitted payload satisfies every per-layer RMSE limit and byte ceiling, and the selected mixed-precision plan minimizes packed bytes with the stated RMSE tie-break. |
| `completion__manifest_consistency` | Rule test | Reported layer and overall RMSE, source and packed sizes, per-layer bytes, and reduction percentage reconcile to the submitted weights artifact. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
