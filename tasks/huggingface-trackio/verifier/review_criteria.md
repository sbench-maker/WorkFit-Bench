# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__runnable_monitoring` | Rule test | The requested script, local experiment store, and JSON report exist; the script replays successfully, every configured run is finalized, and the store is queryable through the bundled experiment CLI without remote services. |
| `completion__metric_fidelity` | Rule test | Every configured run preserves its supplied configuration and records all required per-step and observed validation metrics at the correct steps without inventing missing validation values. |
| `completion__alert_behavior` | Rule test | Error and warning alerts fire at the first qualifying step under the supplied policy, are deduplicated by diagnostic type, and do not misclassify transient or healthy runs. |
| `completion__report_metrics` | Rule test | The incident report covers every configured run exactly once and gives correct latest and best observed validation metrics while reflecting the run's alert count. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
