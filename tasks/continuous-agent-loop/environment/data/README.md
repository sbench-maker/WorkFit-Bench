# HelioLedger SDK 4.6 frozen campaign snapshot

All names and records in this directory are fictional and locally generated. `campaign.json` fixes the campaign, decision signals, budget, snapshot ID, and reporting time. `operating_policy.json` is the release team's governing policy. `gate_catalog.json` defines which blocking checks apply to each risk tier. `rfcs.json` and `work_items.json` define the decomposition and dependency DAG.

`attempts.csv` records bounded unit attempts; `eval_results.csv` contains every gate outcome for those attempts; `merge_queue.csv` is the protected-branch queue snapshot; and `session_state.json` is the persisted resume point. Use the latest attempt number per work item when assessing its current gates. A skipped gate is not a failure when that gate does not apply to the item's risk tier.

The recovery-plan consumer is representation tolerant, but it needs to identify the campaign and source snapshot, selected loop mode, global run state, one disposition for every work item, topological restart waves, applicable gates and attempt allowance for each scheduled unit, budget use, stop controls, a resumable generation/checkpoint, and any release-lead decisions. Every non-routine disposition should carry a concise reference to the observed queue, attempt, gate, failure-signature, or dependency evidence that motivated it.
