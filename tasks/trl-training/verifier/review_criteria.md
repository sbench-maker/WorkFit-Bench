# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The five handoff artifacts named in the local run notes exist, are readable and non-empty, and the launch script is executable. |
| `completion__dataset_quality_traceability` | Rule test | Prepared train/eval data contains every and only eligible pair, preserves source content and IDs, isolates prompt groups by split, and accounts for each exclusion under the stated precedence. |
| `completion__training_configuration` | Rule test | The configuration uses the supplied local assets and requested hyperparameters, fits the two-GPU limit, reaches the required effective batch, and disables remote integrations. |
| `completion__operational_preflight` | Rule test | The executable launcher invokes the DPO command with the bundle configuration, completes the installed offline preflight, and performs no runtime fetch, install, or upload. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
