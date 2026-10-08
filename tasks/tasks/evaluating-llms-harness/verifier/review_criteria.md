# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__benchmark_measurements` | Rule test | Per-benchmark checkpoint and reference means and uncertainty are correctly aggregated from compatible seeds, and checkpoint deltas versus the external baseline are correct across the required suite. |
| `completion__comparability_handling` | Rule test | Failed or protocol-incompatible runs are identified with useful reasons and excluded from the affected aggregate counts without excluding valid runs. |
| `completion__release_decision` | Rule test | The report recommends the highest-step checkpoint that passes every supplied release gate and explicitly holds the newer checkpoint that fails policy. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
