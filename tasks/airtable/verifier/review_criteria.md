# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__base_state_correctness` | Rule test | The persisted Issues table contains exactly the records and field values implied by the frozen base, import, schema choices, and sync policy, without duplicate External IDs or erased optional values. |
| `completion__receipt_reconciliation` | Rule test | Each distinct incoming External ID is classified once in the correct outcome group, category counts agree, and post-sync total and Status counts reconcile to the final base. |
| `completion__rest_transition_safety` | Rule test | The base audit shows schema-first inspection, complete paginated reads before and after mutation, and successful bounded batch upserts merged on External ID only for records that should change. |
| `completion__rejection_actionability` | LLM Judge | Rejected items have concise, issue-specific explanations and the receipt gives a practical next step for correcting and safely rerunning the import without burying the triage signal. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
