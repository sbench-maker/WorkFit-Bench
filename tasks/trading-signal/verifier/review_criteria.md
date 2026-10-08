# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The requested JSON exists, is readable, and exposes identifiable buy, sell, and incomplete-signal collections. |
| `completion__buy_selection` | Rule test | The buy queue contains exactly the policy-eligible top signals in the correct priority order, excluding stale, completed/timeout, low-conviction, high-exit, undersized, and incomplete records. |
| `completion__sell_alerts` | Rule test | Every recent qualifying sell signal that matches an open position is included once, ranked by the policy, and unrelated or incomplete signals are excluded. |
| `completion__metric_fidelity` | Rule test | Actionable rows remain traceable to their source signals; reported trigger/current prices, current return, max gain, exit rate, and smart-wallet conviction agree with source values and use percentage units correctly. |
| `completion__data_quality` | Rule test | Qualifying signals with missing required market data are identified with their actual missing fields and are not promoted into actionable queues with invented values. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
