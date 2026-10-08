# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__deliverable_usability` | Rule test | All five requested Markdown files exist at the requested location, are readable, and contain substantive planning content. |
| `completion__factual_grounding` | Rule test | The plan uses the supplied baseline and competitor scope, addresses the material current-site faults, and does not erase launch-state distinctions that would make public claims misleading. |
| `completion__roadmap_feasibility` | LLM Judge | The phased roadmap has usable owners, dependencies, resource estimates, reserved capacity, launch-aware timing, measurable KPI checkpoints, and risk responses that make the plan executable over 12 months. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
