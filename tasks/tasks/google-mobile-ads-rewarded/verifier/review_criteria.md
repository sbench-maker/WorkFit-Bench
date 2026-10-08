# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_contract` | Rule test | The requested Java file is readable, compiles against the bundled app and offline SDK model, and preserves the starter controller's drop-in public contract. |
| `completion__reward_integrity` | Rule test | The wallet is credited only after the earned-reward callback, with the SDK-provided type and amount unchanged, and receives nothing for show, dismissal, or presentation failure alone. |
| `completion__callback_recovery` | Rule test | UI changes originating in SDK callbacks are marshalled through the view's UI dispatcher, and dismissal or presentation failure retires the used ad and begins replacement loading. |
| `completion__loading_readiness` | Rule test | The controller requests the configured rewarded placement, registers full-screen callbacks, never auto-presents, and exposes the opt-in action only when inventory is ready. |
| `completion__explicit_opt_in` | Rule test | A ready ad is shown only by the explicit watch-button entry point and cannot be reused or shown twice while being consumed. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
