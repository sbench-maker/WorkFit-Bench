# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__tier_capture` | Rule test | The router phase reads the configured header case-insensitively, normalizes known tier values, and stores the configured default for missing, blank, or unknown tiers. |
| `completion__execution_policy` | Rule test | Query and mutation plans use the correct effective ceiling, allow equality, and reject excess cost with the configured status, message, code, and numeric cost extensions. |
| `completion__service_control_flow` | Rule test | Disabled hooks preserve inner service behavior, allowed requests invoke the inner service once, and rejected requests short-circuit it. |
| `completion__workspace_build` | Rule test | The requested checkout and integration files exist, are readable, and compile against the supplied local router interfaces with Cargo offline. |
| `completion__router_integration` | Rule test | The plugin is exported, registered as acme.query_budget, and configured consistently with the supplied local policy. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
