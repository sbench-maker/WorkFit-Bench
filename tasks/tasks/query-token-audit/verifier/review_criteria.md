# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__request_scope_identity` | Rule test | Every queued swap is reviewed exactly once and remains tied to the correct chain, contract, and audit request. |
| `completion__risk_disposition` | Rule test | Usable audits expose the correct risk level and receive the action dictated by the ordered desk policy, including risk-level and tax-based escalation. |
| `completion__tax_interpretation` | Rule test | Usable audits preserve buy and sell tax values and classify acceptable, warning, critical, boundary, and unknown values correctly. |
| `completion__audit_validity` | Rule test | Unavailable or unsupported audits are marked unavailable and do not expose the stale-looking risk, tax, or risk-item fields retained in those snapshots. |
| `completion__summary_reconciliation` | Rule test | The summary's queue total, usable and unavailable counts, and disposition counts reconcile exactly to the submitted detailed reviews. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
