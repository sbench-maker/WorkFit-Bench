# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_and_command_usability` | Rule test | The Markdown deliverable is readable and its emitted commands are syntactically complete, consistently use the detected plugin namespace, and contain no invented command flags or unresolved placeholders. |
| `completion__plan_coverage_and_scope` | Rule test | The overview covers all seven source steps, while detail and batch commands cover steps 2 through 6 in plan order and exclude unrequested steps. |
| `completion__agent_chain_decisions` | Rule test | Each step uses a valid, deduplicated chain in the right order for its intent, including Python review and the PyTorch-specific resolver implied by the project fixture, with overview and commands agreeing. |
| `completion__prompt_fidelity` | LLM Judge | Every scoped task description is executable without reopening the plan, faithfully carries the step's concrete work and 1–3 verifiable completion conditions, and preserves only the out-of-scope boundary declared for that step. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
