# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_and_map_integrity` | LLM Judge | Both requested artifacts are readable; the plan exposes pages and links, and the HTML is a substantive interactive visualization of the requested topic without a remote script dependency. |
| `completion__serp_page_targeting` | Rule test | Every supplied keyword has one traceable disposition, navigational terms are excluded, high-overlap variants share pages, materially different SERPs remain separate, and merged pages use defensible primary targets. |
| `completion__hub_spoke_architecture` | Rule test | The broad seed is the pillar and the derived page targets form coherent, policy-sized spoke clusters consistent with the supplied SERP-overlap bands. |
| `completion__internal_link_network` | Rule test | The link matrix resolves to planned pages, connects every spoke bidirectionally with the pillar, supplies enough incoming paths, uses descriptive anchors, and represents the strongest cross-cluster bridges. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
