# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_and_3p_contract` | Rule test | The requested Markdown artifact is readable, identifies the Workplace Systems Reliability reporting week, and contains distinguishable Progress, Plans, and Problems content. |
| `completion__central_incident_facts` | Rule test | The update accurately communicates the SSO incident's employee and application impact, recovery duration, and linked-ticket disposition at the cutoff. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
