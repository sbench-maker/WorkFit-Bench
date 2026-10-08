# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__canonical_inbox_scope` | Rule test | Every non-terminal work item appears once in the inbox, cross-provider mirrors are merged, and terminal work is absent. |
| `completion__priority_order` | Rule test | The inbox order follows the supplied urgency, active-OKR, recency, impact, blocker, and tie-break rules after mirror merging. |
| `completion__execution_safety_routing` | Rule test | Execution packets are the highest-ranked eligible items, use the unique configured repo and working directory, and unsafe or ambiguous items are routed to review rather than execution. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
