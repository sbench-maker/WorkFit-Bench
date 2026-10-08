# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__workbook_integrity` | Rule test | The requested workbook is readable, retains every source sheet and reference value, and preserves all 240 original trade records and source fields without duplication or alteration. |
| `completion__trade_calculations` | Rule test | Every trade has live formulas for local gross, broker fee in USD, and signed USD cash impact; results follow the supplied rates and settlement rules, cancelled trades resolve to zero cash, and booked trades with missing FX remain explicitly unresolved. |
| `completion__summary_reconciliation` | Rule test | Summary contains each supplied desk/currency combination and a grand total, with live formulas whose counts, fees, cash impacts, and missing-rate states reconcile to Trades. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
