# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_scope` | Rule test | The requested Markdown memo exists, is readable, and contains exactly four identifiable, developed research cards. |
| `completion__pack_traceability` | Rule test | Every card cites valid local IDs, challenges at least one soft or hidden assumption, names a cross-domain mechanism, and grounds the proposal in an observation or available enabler. |
| `completion__structural_creative_depth` | LLM Judge | Each direction maps a distant-domain mechanism through causal or relational correspondences, makes a consequential change to the Mosaic problem representation or constraints, and preserves a relevant boundary condition instead of relying on metaphor. |
| `completion__experimental_discrimination` | LLM Judge | Each card gives a falsifiable prediction and a small experiment whose controls isolate the proposed mechanism, respects the hard deployment envelope or names a missing dependency, and identifies a specific kill risk with an observable failure signal. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
