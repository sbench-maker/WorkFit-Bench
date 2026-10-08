# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_scope` | LLM Judge | The Markdown audit is readable, covers every catalogued component, and reports category-level counts that reconcile with the complete frozen snapshot. |
| `completion__token_audit` | Rule test | Every unauthorized visual literal is tied to its component file and mapped to the exact approved token when one exists; no-match values are surfaced for design review and registered exceptions are not misclassified. |
| `completion__public_naming` | Rule test | All nonconforming public variant and size names are evidenced, mapped to approved aliases, and paired with the supplied nonbreaking deprecation window. |
| `completion__component_completeness` | Rule test | The audit identifies each missing required state or accessibility behavior and each public contract item present in source but omitted from its documentation, with file-level evidence. |
| `completion__risk_prioritization` | LLM Judge | The remediation plan ranks component changes using user impact, reach, and release risk, distinguishes mechanical fixes from design decisions, and sequences public API changes. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
