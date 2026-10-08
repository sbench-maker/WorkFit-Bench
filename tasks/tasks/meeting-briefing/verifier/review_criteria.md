# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__issue_accuracy` | Rule test | Material commercial, legal, security, SLA, transition, approval, and renewal-deadline facts are accurately reconciled across the supplied sources. |
| `completion__continuity_and_gaps` | Rule test | The brief carries forward prior owners/statuses and flags consequential missing, outdated, pending, or unscheduled inputs without turning them into confirmed facts. |
| `completion__meeting_grounding` | Rule test | The brief accurately identifies the target meeting, timing, duration, attendee set, and Ava's role from the calendar and people exports. |
| `completion__prioritization_and_confidentiality` | LLM Judge | The brief prioritizes the time-sensitive negotiation choices and creates a clear, operational boundary between vendor-safe talking points and privileged/internal authority, without leaking the budget ceiling, liability settlement floor, or fallback drafting into external-safe guidance. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
