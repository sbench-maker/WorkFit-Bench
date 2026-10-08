# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__material_scope` | Rule test | The audit identifies the material, directly evidenced debt in pricing, releases, tests, dependencies, documentation, and dispatch durability. |
| `completion__priority_integrity` | Rule test | Finding scores stay on the documented 1–5 scales, use the requested formula correctly, and expose a coherent priority ordering. |
| `completion__plan_integrity` | Rule test | The phased plan accounts for the findings, uses valid references, and does not exceed the debt capacity for now, next, or later. |
| `completion__remediation_value` | LLM Judge | Each material finding connects a concrete customer, delivery, or engineering harm to a proposed remediation. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
