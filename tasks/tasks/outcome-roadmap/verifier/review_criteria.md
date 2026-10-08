# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_structure` | Rule test | The requested Markdown artifact is readable, substantive, and keeps all four 2027 quarter windows visible for planning. |
| `completion__initiative_traceability` | Rule test | Every source initiative ID is retained and associated with its original quarter so teams can trace regrouped outcomes back to the planning pack. |
| `completion__outcome_transformation` | LLM Judge | The roadmap coherently consolidates related outputs and expresses what should change for the relevant customer segment and why that change matters to the business, without simply relabeling the feature list. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
