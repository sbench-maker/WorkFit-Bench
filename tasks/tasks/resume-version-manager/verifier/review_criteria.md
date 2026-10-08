# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__master_and_inventory` | Rule test | The register selects the actual current master and includes every tailored version with its correct base lineage and lineage validity. |
| `completion__application_reconciliation` | Rule test | Every submitted application is represented once with the correct resolution state, resolved version or unresolved candidates, including conflicting and impossible evidence. |
| `completion__update_and_lifecycle` | Rule test | Each version reports the correct linked/open applications, relevant missing updates, and lifecycle action without deleting historical records. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
