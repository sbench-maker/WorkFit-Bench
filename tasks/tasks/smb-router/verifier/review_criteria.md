# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_coverage` | Rule test | The requested JSON is readable, preserves every pending case exactly once, and exposes a next step plus an owner-facing reply for each case. |
| `completion__route_selection` | Rule test | Each present response selects the correct single command or special handling outcome from the request, stored business context, and urgency rules. |
| `completion__connector_safety` | Rule test | Responses distinguish ready, blocked, and onboarding cases correctly, name missing prerequisites, and disclose omitted optional inputs without falsely promising a runnable action. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
