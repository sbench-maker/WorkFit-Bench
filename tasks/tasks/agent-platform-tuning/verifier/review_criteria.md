# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__tuning_dataset` | Rule test | The training and validation JSONL partitions contain every and only the approved, usable, conflict-resolved support example in chat form, without duplicates or holdout leakage, and use the confirmed deterministic 80/20 assignment. |
| `completion__configuration_and_cost` | Rule test | The request uses the confirmed project, region, open model, suitable PEFT hyperparameters and run-prefix URIs, and its cost estimate reconciles to the actual training partition while remaining within budget. |
| `completion__mock_lifecycle` | Rule test | Both exact dataset artifacts are represented as uploaded objects, the receipt is bound to the submitted request, and the same mock job reaches a chronological successful terminal state. |
| `completion__operator_handoff` | LLM Judge | The concise handoff lets an operator locate the run artifacts, understand the staged model/configuration, cost-versus-budget result, and terminal job status, and clearly distinguishes mock success from real cloud tuning or deployment while giving a safe next review step. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
