# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__grounded_reconnaissance` | LLM Judge | The guide identifies the repository's actual application shape and directs the engineer to commands that exist in current configuration rather than the stale prototype note. |
| `completion__instruction_preservation` | Rule test | The new CLAUDE.md retains all three existing project-specific safety rules and adds current, actionable repository guidance without adopting the obsolete prototype stack. |
| `completion__request_lifecycle` | LLM Judge | The guide gives a coherent end-to-end approval path from the web request through validation, authorization, locking, domain policy, the transactional outbox and commit, response serialization, and post-commit worker behavior, without relocating provisioning into the request handler. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
