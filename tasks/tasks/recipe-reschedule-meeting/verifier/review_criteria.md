# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The requested JSON exists, is readable, identifies the affected event, exposes an updated event interval, and—if it declares a status—shows a completed or accepted update. |
| `completion__event_selection` | Rule test | The update targets the one active primary-calendar occurrence matching the request's summary, current time, date, and organizer, without updating a same-name decoy, another occurrence, or the recurring series. |
| `completion__time_transition` | Rule test | The receipt shows the selected occurrence moving from its actual old interval to September 18 at 2:30 p.m. America/Los_Angeles, with the original 75-minute duration and requested IANA timezone on both boundaries. |
| `completion__detail_preservation` | Rule test | The updated occurrence retains its summary, status, organizer, attendee roster, location, description, conference data, reminders, visibility, and recurrence identity while only the time changes. |
| `completion__notification_dispatch` | Rule test | The update uses all-attendee notification semantics, preserves the invitee set, and any explicit delivery list contains every current attendee and no additional recipient. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
