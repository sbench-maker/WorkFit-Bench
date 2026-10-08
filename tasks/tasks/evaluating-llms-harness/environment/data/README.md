# Frozen benchmark exports

These fictional files are a local snapshot of repeated `lm-evaluation-harness` runs. `models.json` identifies five training checkpoints, the current Aurora release, and the external Borealis baseline. `harness_runs.jsonl` contains one exported task result per model, benchmark, and seed; scores are proportions and higher is better.

Use `evaluation_protocol.json` as the release contract. A run is comparable only when it is completed, has a numeric score, uses the required task metric/version/few-shot setting, and matches every required run-config field. Exclude other rows rather than silently averaging them, and retain their `run_id` with the mismatch or failure. Aggregate compatible seeds as specified before applying all release gates. Reference deltas are candidate mean minus reference mean for the same benchmark; macro scores are unweighted means across the required benchmark means.

All entities and observations in this snapshot are synthetic.
