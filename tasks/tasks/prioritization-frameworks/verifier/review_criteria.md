# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_scope` | Rule test | The requested JSON is readable and exposes every catalogued customer problem and proposed initiative, including the withdrawn item as an exclusion rather than silently dropping it. |
| `completion__opportunity_prioritization` | Rule test | Opportunity Scores and problem ranks correctly reflect the declared filtering, latest-valid de-duplication, normalization, segment weights, and tie breaks. |
| `completion__rice_comparison` | Rule test | Every eligible initiative has the correct RICE value and candidate rank from mapped problem opportunity, reach, confidence, and effort; the withdrawn idea is not inserted into that ranking. |
| `completion__q4_portfolio` | Rule test | The recommended set follows the declared ranked walk and remains within 14 person-months, includes dependencies, respects mutual exclusivity, and excludes the withdrawn idea. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
