# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__deliverable_integrity` | Rule test | The unified patch applies safely to the supplied checkout, leaves valid JavaScript, and the requested handoff is present and readable. |
| `completion__interaction_fidelity` | Rule test | Card, halo, and drawer endpoints and public states remain consistent with the bundled interaction contract, including zero-duration reduced-motion behavior. |
| `completion__hot_path_efficiency` | Rule test | High-frequency pointer updates and visible-card reveals produce bounded animation work, do not interleave layout reads and animation writes, avoid layout-changing animated properties, and do not replay completed reveals. |
| `completion__lifecycle_efficiency` | Rule test | A resize burst eventually causes a bounded refresh, and cleanup prevents pending or later events from creating animation work, changing state, or refreshing layout. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
