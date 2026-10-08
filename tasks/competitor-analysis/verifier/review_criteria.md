# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_scope` | LLM Judge | The JSON brief is readable and exposes direct-competitor profiles with position, strengths, weaknesses, pricing, and threats, plus differentiation opportunities and a positioning recommendation. |
| `completion__direct_set` | Rule test | The five direct competitors match the frozen market definition, while component tools, self-host-only products, and non-overlapping enterprise or mobile products are not presented as direct. |
| `completion__pricing_snapshot` | Rule test | Each direct competitor's pricing reflects the Team offer in force on the snapshot date and does not substitute superseded or future announced prices. |
| `completion__evidence_integrity` | LLM Judge | Material claims use a substantive set of local citations that resolve to evidence in force at the snapshot date; any supplied value for a missing fact remains explicitly unknown. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
