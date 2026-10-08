# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__ticket_decisions` | Rule test | Each of the ten instructions has exactly one correct outcome. Executable instructions have the correct filled or open status; instructions blocked by T+1 sellability, price limits, stale quotes, or board-lot constraints are rejected with the corresponding reason. |
| `completion__broker_state` | Rule test | Cancellations release reserved cash. Fills update cash and lot-level positions using the correct prices and fees. A queued limit-up order retains its reserved cash. The default account and other accounts remain unchanged. |
| `completion__report_reconciliation` | Rule test | The account, positions, orders, and trade receipts in output.json match the persisted state and include every business record created or cancelled by this work order. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
