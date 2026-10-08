# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__new_presentation_identity` | Rule test | Exactly one new presentation has the requested title, while the same-title older deck and other existing presentations remain present and unchanged. |
| `completion__initial_slide_content` | Rule test | The new deck contains the three requested slides in briefing order, with every title, subtitle, metric, site, date range, and decision point from the local brief represented on the appropriate slide. |
| `completion__editor_permission` | Rule test | The specified pilot operations user has editor access on the newly generated presentation ID, no broad public or domain grant is added, and permissions on old files are untouched. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
