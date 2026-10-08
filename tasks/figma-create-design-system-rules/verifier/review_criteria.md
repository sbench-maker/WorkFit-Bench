# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_and_preservation` | Rule test | The requested AGENTS.md is readable and ready to use, retains all material pre-existing contributor safeguards, and contains no unresolved template placeholders. |
| `completion__component_architecture` | Rule test | The rules correctly distinguish reusable primitives from feature composition and encode the repository's naming, export, import, component API, routing, state, and data-access boundaries. |
| `completion__styling_tokens_assets` | LLM Judge | The rules direct implementations to the actual CSS Module and token systems and give correct, non-destructive handling for Figma-provided and persisted assets. |
| `completion__figma_workflow` | Rule test | The rules encode the captured node-context, truncation fallback, screenshot, implementation gating, translation, and parity-validation flow in the correct dependency order. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
