# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_prd_contract` | Rule test | The requested Markdown file is readable, substantial, and covers the core decision areas needed in a PRD: context, owners, goals, users, value, solution, assumptions, and release planning. |
| `completion__evidence_and_objectives` | Rule test | The PRD reports the eligible manual-work baseline correctly and preserves the approved week-six speed, quality, adoption, authorization, and audit outcome contract. |
| `completion__safe_v1_contract` | Rule test | v1 keeps the single-queue 50-ticket routing workflow, preview and partial-result protections, permissions, idempotency, audit, and accessibility needs, while materially riskier asks remain outside v1. |
| `completion__solution_release_decisions` | LLM Judge | The proposed experience, requirements, measurement plan, dependencies, gates, and relative release sequence form an implementable path from prototype through dogfood, pilot, and launch decision. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
