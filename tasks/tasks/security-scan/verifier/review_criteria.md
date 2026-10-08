# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__finding_correctness` | Rule test | The assessment identifies the material permission, instruction-injection, MCP, hook, exfiltration, error-suppression, and agent-definition weaknesses in the frozen configuration, ties them to the correct files, and assigns defensible severity levels. |
| `completion__remediation_quality` | LLM Judge | Remediations are specific enough for the repository team to act on, reduce the cited attack path without recommending blanket disablement of safe controls, and keep credential-like values out of evidence and examples. |
| `completion__safe_control_precision` | Rule test | The report recognizes the existing deny rules, pre-tool guard, restricted local MCP setup, and least-privilege agents without misclassifying safe-only definitions as vulnerabilities. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
