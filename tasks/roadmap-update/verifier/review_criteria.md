# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__portfolio_scope_status` | Rule test | Every frozen initiative plus the requested addition appears once in the updated roadmap with a source-traceable ID and a status consistent with the packet's frozen state. |
| `completion__planning_constraints` | Rule test | The updated horizon assignments place the audit export by its deadline, propagate the vendor slip through dependent work, preserve all hard deadlines, respect dependency order, and stay within every team/horizon capacity. |
| `completion__change_accounting` | Rule test | The change record identifies the addition and every initiative whose updated horizon differs from the source, with its prior and new state aligned to the roadmap itself. |
| `completion__risk_actionability` | LLM Judge | The updated roadmap names material blocked and at-risk chains with their blockers, owners, timing, affected stakeholders, and a mitigation or checkpoint. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
