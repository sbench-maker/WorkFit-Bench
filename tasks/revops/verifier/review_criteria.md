# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_coverage` | Rule test | The JSON handoff plan is readable and contains exactly one identifiable decision for every contact in the frozen CRM snapshot. |
| `completion__scoring_lifecycle` | Rule test | Fit, engagement, negative signals, disqualifiers, account resolution, and resulting lifecycle outcomes follow the supplied CRM facts and operating policy. |
| `completion__routing_capacity` | Rule test | MQL ownership follows routing precedence, preserves eligible continuity, respects availability and projected capacity, and queues cases only when no eligible rep remains. |
| `completion__sla_actions` | Rule test | Handoff times, first-contact deadlines, observed contact status, escalation state, and next actions are consistent with the supplied calendar and activity history. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
