# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__qualified_scope` | Rule test | The artifact contains exactly the locations that satisfy the campaign's geographic, category, rating, review, website, and business-email requirements after location-level deduplication. |
| `completion__business_fidelity` | Rule test | Each delivered lead carries the requested CRM business fields and their values agree with the selected source listing. |
| `completion__contact_dedup_integrity` | Rule test | Delivered emails are usable website-domain contacts, duplicate location representations are collapsed using the brief's winner rule, and distinct branches sharing a domain remain separate. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
