# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The requested repository and refactor notes are present, readable, and the Python sources compile. |
| `completion__public_api_behavior` | Rule test | Public imports, quote calculations, manifest ordering and atomic validation match the original package across the frozen cases and independent boundary probes. |
| `completion__cli_compatibility` | Rule test | Single-quote, usage, and mixed JSONL batch commands preserve parsed output, error-line numbering, continuation, stdout/stderr behavior, and exit status. |
| `completion__validation_boundaries` | Rule test | Type checks, range limits, same-day restrictions, rounding thresholds, surcharge order, and exact public error messages remain unchanged. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
