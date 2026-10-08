# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_scope` | Rule test | The requested Markdown report exists, is readable, covers both comparison months and all four supplied channels, and includes the explicitly requested September decision section. |
| `completion__metric_accuracy` | Rule test | July/August totals, changes, channel efficiency metrics, and target comparisons agree with the frozen daily data and targets after representation-neutral normalization. |
| `completion__attribution_handling` | Rule test | The report quantifies the Paid Social coverage gap, keeps reported and coverage-adjusted revenue/ROAS distinct, and reaches the correct target interpretation without presenting the estimate as observed revenue. |
| `completion__trend_interpretation` | LLM Judge | The report identifies the decision-relevant inflections in each channel, connects them to dated campaign/event evidence with appropriately cautious causal language, and distinguishes sustained movement from the webinar concentration, syndication spike, and tracking artifact. |
| `completion__decision_support` | LLM Judge | The report gives exactly three September priorities, each tied to a diagnosed channel issue and a practical follow-up measure or action. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
