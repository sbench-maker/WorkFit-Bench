# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__tracker_and_snapshot` | LLM Judge | The plan applies exactly the eligible latest Orbit task updates and reports the resulting status counts, overdue open work, and active blockers. |
| `completion__calendar_coordination` | Rule test | Every unscheduled meeting request is placed at the earliest feasible time with the correct recurrence and attendees, while the existing request is not duplicated and the sensitive review excludes its optional observer. |
| `completion__email_routing` | Rule test | The plan drafts the current weekly status email and only the blocker escalation that is due after cooldown, with the correct stakeholder and escalation recipients and reviewable subject/body content. |
| `completion__document_workflow` | Rule test | The plan uploads and announces only the newest approved, team-visible, not-yet-announced Orbit runbook version to the project channel. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
