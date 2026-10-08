# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__execution_contract` | Rule test | The named pipeline runs offline, creates readable score and metric artifacts, and recomputes from a relocated corrected fixture instead of embedding visible answers. |
| `completion__remote_workflow` | Rule test | The pipeline reads the three BigQuery tables through DataFrame APIs, joins them remotely, enables requested partial ordering, and invokes remote model operations without downloading source tables. |
| `completion__model_training` | Rule test | The persisted logistic model uses the documented deduplicated June-August cohort, label distribution, and complete feature contract. |
| `completion__evaluation_metrics` | Rule test | metrics.json identifies the model and accurately reports row count, ROC AUC, accuracy, and log loss returned by its evaluation. |
| `completion__scoring_output` | Rule test | churn_scores.csv covers every eligible September account exactly once, excludes ineligible accounts, contains correct probabilities, and is ordered by descending risk. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
