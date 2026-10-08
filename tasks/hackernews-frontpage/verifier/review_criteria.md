# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_contract` | Rule test | The requested JSON exists, is readable, contains a story collection and total count, and exposes the six requested values for every story with usable types. |
| `completion__coverage_and_order` | Rule test | All and only the 30 ranked stories appear once, in displayed order, with the reported total consistent with the collection. |
| `completion__story_identity` | Rule test | Each extracted item ID is paired with the correct decoded visible title and destination link from its ranked row. |
| `completion__engagement_metadata` | Rule test | Scored stories have the correct numeric points and comments, including singular labels and zero-comment discuss links. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
