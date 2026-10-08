# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_contract` | Rule test | The requested project exists, runs through its existing CLI, and returns the documented top-level and result structure. |
| `completion__discovery_hydration` | Rule test | A query is sent to search before exactly the three selected usable pages are scraped, using the mock service contract. |
| `completion__ranking_failure` | Rule test | Selected results preserve search order, retain discovery metadata, and one scrape failure does not block successful pages. |
| `completion__configuration_security` | Rule test | The configured self-hosted base URL and bearer credential are used, trailing slashes are safe, and no credential is committed or leaked. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
