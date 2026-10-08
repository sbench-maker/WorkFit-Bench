# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__workflow_preservation` | Rule test | The output is a readable deployable workflow export that retains the supplied workflow identity, node inventory, node identities, positions, and connection graph while remaining inactive. |
| `completion__operation_dependencies` | Rule test | Versioned node parameters correctly implement the webhook, unary IF, GET query, POST JSON body, and response-building requirements without stale hidden fields. |
| `completion__database_security_release` | Rule test | The database UPSERT binds dynamic values, is explicitly transactional, keeps downstream execution alive, and the inactive export contains no fabricated credential bindings. |
| `completion__routing_responses` | Rule test | Approved, waitlist, invalid, and unexpected inputs have identifiable handling, correct explicit HTTP outcomes, a non-dropping Switch fallback, and a correctly shaped coordinator alert. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
