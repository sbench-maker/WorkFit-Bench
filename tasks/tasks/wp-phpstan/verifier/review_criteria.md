# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__configuration_and_change_boundaries` | Rule test | The analysis covers first-party plugin code without generated or vendored noise, retains WordPress core discovery, and leaves the baseline and Composer dependency set unchanged. |
| `completion__wordpress_type_correctness` | Rule test | REST request parameters, the WooCommerce hook callback, database result rows, and scheduler arguments have types consistent with how the supplied code uses them, including a non-null database collection result. |
| `completion__third_party_resolution_safety` | Rule test | The installed WooCommerce stubs are used, the absent optional loyalty API is handled narrowly, and no suppression can mask unrelated unknown classes. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
