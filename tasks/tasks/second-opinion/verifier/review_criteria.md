# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_and_reviewer_coverage` | Rule test | The requested JSON is readable and contains separately attributable, non-empty findings from both local reviewers. |
| `completion__material_findings` | Rule test | The reviewer-specific sections capture the tenant cache leak, unsafe fallback, oversized-request batching regression, and metadata authorization bypass found by the two frozen review responses, with risk-appropriate severity. |
| `completion__patch_scope_and_citations` | Rule test | Findings stay within files changed from main and material issues cite the relevant changed lines rather than legacy code. |
| `completion__comparison_consistency` | Rule test | The comparison correctly distinguishes issues shared by both reviewers from Codex-only and Gemini-only findings. |
| `completion__merge_gate` | Rule test | The consolidated result clearly recommends blocking the merge until the material regressions are fixed. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
