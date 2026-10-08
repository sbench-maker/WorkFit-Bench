# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__packet_usability` | Rule test | Both requested files open successfully, identify Harbor & Pine Studio and April 2026, keep the PDF to one page, and expose the four close schedules described by the local close notes. |
| `completion__reconciliation_accuracy` | Rule test | Every available April processor settlement and QuickBooks deposit is represented once with the correct match, gap category, amounts, and variance, and the unavailable PayPal feed is clearly scoped out. |
| `completion__flagged_workflow_fidelity` | Rule test | The flagged schedule covers every uncategorized transaction, possible duplicate, and missing receipt, and faithfully carries the owner's approved or open disposition without silently fixing source exports. |
| `completion__financial_statement_accuracy` | Rule test | The March-versus-April P&L uses posted QuickBooks lines plus approved triage adjustments, includes source-derived categories and reconciled subtotals, and reproduces the balanced April 30 trial balance. |
| `completion__summary_consistency` | Rule test | The one-page PDF reports the same April revenue, gross margin, net income, and remaining reconciliation-gap count as the detailed close schedules. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
