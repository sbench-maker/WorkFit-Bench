# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__gate_and_blocker_coverage` | Rule test | The release is held and all six independently actionable production gaps are represented: runner version, build backend, action pinning, cache protocol, OIDC audience, and artifact host allowlisting. |
| `completion__technical_comparison_accuracy` | LLM Judge | Observed and required versions, satisfied prerequisites, advisory threshold, and migration deadline agree with the frozen candidate and page bodies. |
| `completion__source_traceability` | LLM Judge | The compatibility, security, migration, and identity conclusions trace to the four complete current source pages that support them. |
| `completion__evidence_conflict_handling` | LLM Judge | The handoff explains why the superseded 5.4.1 draft, archived July exceptions, partial FAQ, and blocked social pages cannot override current complete guidance, without treating search snippets as proof. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
