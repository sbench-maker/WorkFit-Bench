# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_runnable` | Rule test | The requested Ruby spec exists, loads against the bundled Rack app, defines the requested feature scenarios, and passes against the reference behavior. |
| `completion__successful_checkout` | Rule test | The feature coverage detects materially wrong promotion totals and a missing order-confirmation state in the search-to-purchase journey. |
| `completion__sold_out_protection` | Rule test | The feature coverage detects when a sold-out event becomes selectable or purchasable instead of remaining visibly unavailable. |
| `completion__invalid_promo_protection` | Rule test | The feature coverage detects when SUNSET10 is incorrectly accepted and discounts the two-ticket total. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
