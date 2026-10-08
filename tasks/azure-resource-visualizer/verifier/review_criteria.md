# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__resource_scope` | Rule test | All 40 current in-group resources are accounted for in the document and topology, while the three cross-group resources appear as clearly external context rather than being folded into the inventory. |
| `completion__topology_correctness` | LLM Judge | The Mermaid topology maps the verified runtime, network, hosting, identity, observability, and external relationships, labels their meaning, deduplicates corroborating observations, and does not assert candidate or inactive links as current fact. |
| `completion__configuration_accuracy` | Rule test | Resource SKU, region, and material architecture settings agree with the snapshot, remain associated with the correct resource, and the document does not fabricate credential values. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
