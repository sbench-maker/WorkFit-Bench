# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__module_architecture` | Rule test | The left-to-right dependency map covers the service's material modules and direct dependency relationships without obscuring its handler, security, pipeline, repository, rendering, and runtime boundaries. |
| `completion__execution_paths` | Rule test | The attack-surface view contains each request handler that can reach run_template, shows the material intermediates, and does not invent call relationships between code functions. |
| `completion__trust_encoding` | Rule test | The public receive and preview handlers are visibly distinguished as untrusted from the authenticated replay handler in the attack-surface view. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
