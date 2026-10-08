# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The requested JSON exists, is readable, represents a completed successful crawl, and contains a page collection. |
| `completion__scope_coverage` | Rule test | The export contains exactly the reachable in-scope pages for the stated start section, depth, path exclusions, and page cap. |
| `completion__content_fidelity` | Rule test | Each exported page carries the correct title and complete Markdown content from the frozen site snapshot. |
| `completion__crawl_consistency` | Rule test | Canonical URLs are unique, recorded link depths are correct and within five hops, excluded branches are absent, and reported totals agree with the page collection. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
