# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__scope_coverage` | Rule test | Every entrypoint in the supplied scope inventory is accounted for with a finding link or an explicit no-material-issue outcome. |
| `completion__material_detection` | Rule test | The report identifies the source-grounded release risks in swap protection, fee authorization, reserve math, vault donation and token accounting, vault reentrancy/CEI, public synchronization, and oracle pricing. |
| `completion__risk_consistency` | Rule test | Detected risks are not materially understated and the deployment decision blocks a launch containing reachable high or critical issues. |
| `completion__safe_path_discrimination` | Rule test | The entrypoint ledger distinguishes the fixture's guarded, role-gated, safe-transfer, measured-accounting, and two-step-admin paths from vulnerable paths. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
