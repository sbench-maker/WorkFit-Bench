# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__decomposition_and_recovery` | Rule test | All twelve approved requirements have one accountable active owner with the correct repository scope and minimum risk; unaffected identities are preserved while the stalled worker is retired into three narrower successors. |
| `completion__dag_and_merge_safety` | Rule test | The active graph is complete and acyclic, declares every RFC prerequisite, and queues each unmerged unit only after dependencies, gates, and rebasing can be satisfied; merged and retired work are excluded. |
| `completion__validation_and_release_gates` | Rule test | Every unit uses cataloged acceptance checks and honest six-stage gate states, every queued merge reruns the required eligible tests, and final verification covers all system suites plus the cohort-disable history rehearsal. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
