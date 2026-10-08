# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__identity_resolution` | Rule test | The brief resolves Maya Chen to the Northstar Grid contact and reports her core identity without mixing in the same-name records. |
| `completion__engagement_evidence` | LLM Judge | Contact-initiated activity and website interest use the snapshot windows, cover the material in-window signals, and distinguish excluded team or out-of-window records. |
| `completion__enrichment_evolution` | LLM Judge | The brief reports the returned raw scores and all Spark records as a chronological evolution rather than collapsing them into one snapshot. |
| `completion__account_context` | LLM Judge | The brief accurately describes the material Northstar Grid expansion context and compares Maya with the contacts who actually initiated recent activity. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
