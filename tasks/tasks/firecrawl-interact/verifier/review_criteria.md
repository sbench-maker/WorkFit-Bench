# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact` | Rule test | The requested JSON exists, parses, and exposes a ticket collection and summary. |
| `completion__selection` | Rule test | Every and only open urgent ticket beyond its SLA is included once. |
| `completion__details` | Rule test | Included tickets preserve the available drawer details, calculated breach age, and blank-owner meaning. |
| `completion__summary` | LLM Judge | Overall, regional, and unassigned counts agree with the selected tickets. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
