# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_execution` | Rule test | The requested JavaScript exists, executes once against a batch through the n8n input contract, and returns usable n8n items with one summary. |
| `completion__quarantine_resilience` | Rule test | Malformed physical deliveries and selected cancellations are quarantined with applicable reasons, while empty input is handled without a batch failure. |
| `completion__summary_reconciliation` | Rule test | The one summary reports exact input, canonical, retry, ledger, and quarantine counts plus signed per-currency cent totals, including the zero batch. |
| `completion__ledger_transformation` | Rule test | Every selected paid/refunded event appears once with the correct latest-valid retry, trimmed identifiers, UTC timestamp, currency, sign, and exact cent amount. |
| `completion__source_linkage` | Rule test | Each ledger or quarantine detail links to the exact physical input delivery that produced it. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
