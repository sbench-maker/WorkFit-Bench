# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_scope` | LLM Judge | The requested JSON is readable and contains identifiable coverage of both site profiles, anchor analysis, toxic-link review, linked pages/reclamation, competitor gap, and snapshot limitations. |
| `completion__profile_accuracy` | LLM Judge | Active backlink and referring-domain totals, follow share, inferred anchor distribution, referring-domain quality evidence, and leading linked pages agree with the frozen export for both sites. |
| `completion__gap_evidence` | LLM Judge | The competitor-only gap is correctly represented and every ranked prospect is truly competitor-only, viable, capped at ten, and backed by correct source metrics. |
| `completion__risk_and_edge_safety` | Rule test | All CipherLeaf referring domains with direct manipulation, penalty, deindexing, hacked-content, or link-farm evidence are separated as disavow candidates, while competitor-only risk domains are excluded from outreach rather than mislabeled as CipherLeaf disavow actions. Nofollow/low-authority-only domains are not disavowed; JS-unverifiable links remain unknown and active links to 404 destinations are surfaced for reclamation. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
