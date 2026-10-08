# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_completeness` | LLM Judge | The requested Markdown deliverable is readable, substantial, covers all six numbered email slots, and includes a text representation of the flow. |
| `completion__campaign_fidelity` | Rule test | The sequence uses the supplied three-part activation definition, only approved destinations, and avoids expressly disallowed offers or product promises. |
| `completion__journey_control` | LLM Judge | Branches target the earliest incomplete activation step, apply exits and sales transfer before sends, cover every supplied suppression and re-entry concern, and are clear enough to configure without contradictory paths. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
