# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_behavior` | Rule test | Both requested artifacts are readable, and the hardened site retains all three routes, the 240-record local feed, navigation, filtering, greeting, chart, and user-triggered location behavior. |
| `completion__browser_security` | Rule test | The hardened copy prevents untrusted text from reaching execution sinks, avoids insecure or unpinned active resources, enforces an effective response-header policy, and requests location only in context. |
| `completion__compatibility_quality` | Rule test | Every route uses robust HTML5 metadata and valid core nesting, while brittle browser sniffing, parser-blocking APIs, production debug logging, and exposed source maps are removed. |
| `completion__audit_coverage_accuracy` | Rule test | The JSON audit covers each material issue family evidenced by the snapshot, identifies relevant files or locations, and accurately distinguishes remediated code issues from the external session-cookie decision. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
