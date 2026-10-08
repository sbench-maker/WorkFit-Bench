# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__source_resolution` | Rule test | The note identifies the official FluxCache Python 4.2 documentation target and supports each requested topic with valid current-snapshot section IDs. |
| `completion__install_and_client_setup` | Rule test | The note gives a 4.2-compatible asyncio installation constraint and a client setup using the documented async class, environment-backed credential, bounded pool, and request timeout without embedding a credential value. |
| `completion__transaction_resilience` | Rule test | The note shows a stable idempotency key and accurately describes the bounded retry policy, allowed transient errors, backoff behavior, and non-retryable errors. |
| `completion__migration_and_lifecycle` | Rule test | The note removes the material v3 async names, maps them to 4.2 replacements, and gives safe automatic and manual shutdown behavior. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
