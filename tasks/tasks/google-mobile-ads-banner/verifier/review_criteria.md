# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_build` | Rule test | The requested project is present at the named output path, retains its fixture inputs, and completes its offline build. |
| `completion__adaptive_placement` | Rule test | Exactly one inline adaptive banner is placed at the product team's sponsored slot inside the scrolling feed with the development viewport width. |
| `completion__request_loading` | Rule test | The banner sends one load request using the fixture's Android test traffic and the selected adaptive size. |
| `completion__callback_states` | Rule test | Background success and failure callbacks update meaningful status and banner visibility without an off-main-thread UI mutation. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
