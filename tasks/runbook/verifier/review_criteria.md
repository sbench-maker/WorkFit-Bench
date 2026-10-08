# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_scope` | Rule test | The requested Markdown exists, is readable, and clearly addresses RelayForge's production WebhookQueueAgeHigh response in both production regions. |
| `completion__procedure_accuracy` | Rule test | The procedure gathers the required evidence before mutation and maps every observed failure mode to the approved command, limit, and decision boundary in the supplied operational evidence. |
| `completion__safety_and_exit_paths` | LLM Judge | The runbook uses the frozen recovery gates, provides safe reversal instructions, routes material escalation conditions correctly, and rejects superseded destructive guidance. |
| `completion__diagnostic_reasoning` | LLM Judge | The decision flow distinguishes overlapping symptoms, explains why each branch is selected, handles ambiguous or unreliable evidence safely, and connects observed results to the next action without encouraging stacked mitigations. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
