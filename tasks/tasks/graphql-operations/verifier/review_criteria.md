# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__operation_scope` | Rule test | Named operations cover workspace loading/paging, decision submission, and decision-change subscription through the schema's corresponding root fields, without unrelated root operations. |
| `completion__schema_and_variables` | Rule test | The complete document validates against the frozen schema and all field/directive arguments use declared variables rather than embedded request values. |
| `completion__workspace_query` | Rule test | The project query selects exactly the header and asset-grid data consumed by the UI, implements forward cursor pagination, and gates the internal note behind a caller-controlled include directive that is not enabled by default. |
| `completion__write_and_live_updates` | Rule test | The decision mutation handles success, validation, and version-conflict results with the data needed for rendering/cache updates, while the subscription returns the specified event, actor, project, and shared asset state without unused payload fields. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
