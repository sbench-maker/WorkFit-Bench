# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The requested project brief, launch brainstorm prompt, and Sprint 1 plan, progress, and done working documents exist as readable, substantive Markdown in the launch pack. |
| `completion__project_fidelity` | Rule test | The durable brief preserves the fixed product purpose, roles, accepted stack, run-state and metric contracts, and local commands from the frozen inputs. |
| `completion__security_integrity` | Rule test | The pack retains the concrete upload, redaction, and live-provider boundaries and contains no credential-like secret value. |
| `completion__sprint_integrity` | Rule test | Sprint 1 schedules every committed item within capacity, respects dependencies and accountable owners, excludes blocked/rejected/deferred work, and retains the supplied team and merge boundaries. |
| `completion__brainstorm_quality` | LLM Judge | The launch brainstorm prompt assigns distinct perspectives to the named EvalHarbor roles and asks them to challenge assumptions, decide scope or trade-offs, and produce a handoff. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
