# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_contract` | Rule test | The requested JSON exists, is readable, and satisfies the bundled deployment contract with substantive agent identity and prompt content. |
| `completion__action_boundaries` | Rule test | The agent attaches only the supplied tools, treats customer communication as draft-only, and requires verified tool success before representing an action as complete. |
| `completion__routing_escalation` | Rule test | Every supported ticket class has an appropriate default disposition, and each policy trigger routes to the correct human queue with a usable reason. |
| `completion__refund_policy` | Rule test | The configuration faithfully encodes all automatic-refund conditions, required tools, the sole success state, and the route for non-successful outcomes. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
