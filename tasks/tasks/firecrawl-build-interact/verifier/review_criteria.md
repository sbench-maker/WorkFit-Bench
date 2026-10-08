# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | Both requested files exist, parse, and the completed collector retains the documented CLI contract. |
| `completion__primary_results` | Rule test | The primary output contains every and only eligible requested-category controls, with correct record values and no duplicates. |
| `completion__interactive_flow` | Rule test | The integration escalates from scrape to interactions, applies the requested filter, extracts pages, and paginates in one browser session. |
| `completion__reusability` | Rule test | The unchanged collector correctly handles the bundled regression case with different category, IDs, and page size. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
