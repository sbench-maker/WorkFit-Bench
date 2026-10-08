# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__consolidation_scope` | Rule test | The artifact has exactly one consolidated record for every canonical topic and preserves every contributing source record ID on that topic. |
| `completion__authoritative_resolution` | Rule test | Non-conflicted topics retain the correct field-level values under source authority and recency, and every topic is assigned to the policy-defined canonical layer. |
| `completion__sync_decisions` | Rule test | Create, update, noop, and review decisions agree with current target state; all and only blocked topics enter review with the relevant conflicting source or target IDs retained. |
| `completion__navigation_safety` | Rule test | Credential markers are redacted, cross-references are correctly merged, and the project/kind topic index is complete and consistent with the catalog. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
