# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__checkpoint_scope_integrity` | Rule test | Every source checkpoint row appears once with its original shape, and tensors marked ineligible are preserved exactly. |
| `completion__activation_aware_2_4_correctness` | Rule test | Eligible rows keep the two greatest weight-times-aggregated-activation scores in each consecutive group of four, preserve retained source values, zero the rest, and honor deterministic ties. |
| `completion__summary_reconciliation` | Rule test | The concise layer summaries and global validation metrics cover the full model and reconcile with the delivered checkpoint, sparsity pattern, calibration coverage, and exclusions. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
