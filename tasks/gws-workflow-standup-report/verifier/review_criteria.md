# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__agenda_accuracy` | LLM Judge | The agenda contains exactly the eligible report-day meetings with correct core details, chronological ordering, and evidence-based timed conflict flags. |
| `completion__open_work_accuracy` | Rule test | All and only actionable Tasks records appear with correct core facts, while overdue and blocked items are explicitly and correctly flagged. |
| `completion__rollup_consistency` | Rule test | Headline meeting/open/risk counts and owner- and priority-level task summaries reconcile with the eligible source records and report details. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
