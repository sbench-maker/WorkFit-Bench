# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__financial_reconciliation` | Rule test | Annual and cumulative direct, indirect, and total costs reflect the frozen salary, fringe, allowability, timing, classification, MTDC, and F&A rules. |
| `completion__routing_dispositions` | Rule test | Material open issues are surfaced and correctly separated into submission blockers and nonblocking confirm-later items without misclassifying resolved budget corrections. |
| `completion__justification_grounding` | LLM Judge | The narrative explains why the retained cost categories and effort are necessary for the named work, uses proposal-facing language, and handles corrections and documentary contingencies without unsupported claims. |
| `completion__routing_actionability` | LLM Judge | The compliance log is concise and operational: a sponsored-programs reviewer can identify why each listed issue matters, what evidence triggered it, and the next action without reconstructing the analysis. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
