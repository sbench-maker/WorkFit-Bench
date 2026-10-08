# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_scope` | Rule test | The requested JSON handoff is readable, identifies the documentation snapshot, and includes one substantive answer with supporting pages for every queued case. |
| `completion__page_discovery` | Rule test | Each case cites the smallest set of canonical mirror pages needed to support its documented answer, without irrelevant or fabricated URLs. |
| `completion__guidance_accuracy` | LLM Judge | The case answers preserve the operational facts, state transitions, return values, and important negative constraints stated in the cited Markdown snapshots. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
