# Orion-mini pruning fixture

This is a deterministic fictional checkpoint export for an offline serving handoff. `checkpoint_rows.jsonl` contains one output row per tensor; `tensor_manifest.json` declares shapes and eligibility. `calibration_activations.jsonl` contains collected per-sample input RMS vectors. `pruning_contract.json` defines aggregation, importance, 2:4 grouping, tie handling, and preservation rules.

The requested JSON should contain the complete pruned checkpoint, a concise summary for each transformer layer, and validation notes suitable for a serving engineer. A convenient checkpoint row uses `tensor_id`, `output_row`, and `weights`, but equivalent JSON grouping is acceptable when tensor identity, row identity, and values remain clear.
