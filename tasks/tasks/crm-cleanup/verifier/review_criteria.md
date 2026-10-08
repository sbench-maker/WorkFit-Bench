# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__stale_deal_audit` | Rule test | Every and only open deal without qualifying activity in the configured 14-day window is reported, with correct stage, last activity, associated contacts, and amount. |
| `completion__missing_field_audit` | Rule test | The plan reports exactly the configured required-field gaps for open deals and contacts associated with those deals, treating zero as present and paired next-step/notes correctly. |
| `completion__duplicate_candidate_coverage` | Rule test | All contact groups meeting the supplied normalized-email or normalized-company-and-name policy are included, while deliberate near-match decoys are excluded. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
