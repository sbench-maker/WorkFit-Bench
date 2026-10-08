# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__runnable_migration` | Rule test | The delivered project is readable, has a local validation entry point, honors BASE_URL, and its Playwright suite passes against the supplied checkout application without external services. |
| `completion__checkout_calculations` | Rule test | The migrated suite protects the source suite's standard shipping, express shipping, promotion, and threshold calculations so material regressions are detected. |
| `completion__resilience_and_popup` | Rule test | The migrated suite detects loss of out-of-stock blocking, pricing failure feedback, or the receipt's new-tab behavior. |
| `completion__target_project_contract` | Rule test | The result is a TypeScript Playwright Test project that declares its target dependency and contains no Cypress runtime dependency or source API residue. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
