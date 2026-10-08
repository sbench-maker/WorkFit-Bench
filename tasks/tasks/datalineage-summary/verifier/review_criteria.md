# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__upstream_accuracy` | LLM Judge | The report correctly traces the four confirmed current source branches through their important staging and enrichment assets and processing jobs into net_revenue, including the direct calculation inputs. |
| `completion__downstream_accuracy` | Rule test | The report correctly traces net_revenue through both immediate products to all four confirmed current final consumers and names the material processing jobs. |
| `completion__scope_and_boundaries` | Rule test | The report states the focal column and frozen search parameters, covers both direction queries and all captured locations, and accurately flags the inactive legacy paths and unresolved override endpoint. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
