# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The finished workspace and change report exist at the requested paths, are readable, and retain the supplied task and memory artifacts. |
| `completion__task_state_reconciliation` | Rule test | Confirmed tracker additions, activity follow-ups, completions, reschedules, and moves are reflected once in the correct task state, while fuzzy matches are not duplicated. |
| `completion__memory_resolution` | Rule test | Confirmed people, project, status, and relationship context is reflected in memory, while the unresolved acronym remains unexpanded and is surfaced for clarification. |
| `completion__scope_and_evidence_integrity` | Rule test | Untouched workspace records are preserved, no unapproved or other-owner tasks are introduced, and every new task keeps its local source reference. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
