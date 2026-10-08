# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__token_foundations` | Rule test | W3C-shaped tokens preserve the approved palette and provide the foundation categories and scale breadth specified by the local brief. |
| `completion__theme_contract` | Rule test | Light and dark semantic roles resolve to the approved colors, meet the relevant contrast thresholds, and are exposed as CSS variables with explicit and system-preference theme behavior. |
| `completion__component_contracts` | Rule test | All requested components cover the inventory's observed variants and sizes, while Button and TextInput preserve native element props and forwarded refs. |
| `completion__accessible_behavior` | LLM Judge | The component implementations work together to provide the keyboard, focus, labeling, validation, live-region, and dialog behaviors described in the handoff, without relying on color alone. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
