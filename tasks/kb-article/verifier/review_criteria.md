# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__diagnosis_and_applicability` | Rule test | The article identifies the exact MAP-403 symptom, the deactivated saved-mapping owner condition, the administrator and plan scope, and the nearby import cases to which this workaround does not apply. |
| `completion__supported_resolution` | Rule test | The article gives the approved duplicate-and-reassign workflow in executable order, explains how to confirm the import, and provides the supported escalation evidence and privacy boundary. |
| `completion__publishing_and_safety` | LLM Judge | The requested draft is readable, carries usable publication metadata and source/review notes, makes a supported create-versus-update decision, and excludes customer identities, internal codenames, and speculative release claims. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
