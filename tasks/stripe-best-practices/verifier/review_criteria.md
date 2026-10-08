# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The completed checkout-service repository contains the supplied fixture, importable implementation, documented public entry point, and requested handoff file. |
| `completion__checkout_sessions` | Rule test | Pending orders create reconciled one-time Checkout Sessions with configured URLs, order references, distinct tracking labels, and dynamic payment-method eligibility; invalid order states create nothing. |
| `completion__configuration_boundary` | Rule test | The service fails closed without its two deployment-provided values, passes the supplied API key to a client pinned to the mock's current API version, and contains no credential-shaped value in deliverable text. |
| `completion__webhook_trust` | Rule test | Only authentic, timely, paid Checkout events whose order ID, amount, and currency agree with local state can fulfill a pending order; rejected events leave state unchanged. |
| `completion__retry_safe_transitions` | Rule test | Repeated event delivery remains idempotent after rebuilding the service, records an event once, and later events do not regress paid or cancelled terminal orders. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
