# Northstar DPO run handoff

The frozen preference export is intended for a two-GPU Direct Preference Optimization run against the local model directory. The environment has no network access. Do not download a model or dataset, push artifacts, or enable a remote reporter.

## Pair eligibility and split rules

Process every row in `raw_preference_pairs.jsonl`. A pair is eligible only when all of the following are true:

- `consent_for_training` is true and `review_status` is `approved`.
- `prompt`, `chosen`, and `rejected` are non-empty message arrays. Prompt roles may be `system` or `user`; chosen and rejected must each contain assistant messages with non-blank content.
- Chosen and rejected content differ after trimming, collapsing whitespace, and case-folding.
- `estimated_tokens` does not exceed 1,024.
- Its normalized prompt/chosen/rejected triple is not a duplicate of an earlier eligible pair. Keep the lexicographically earliest `pair_id`.

Use exactly one primary exclusion reason per rejected row, applying this precedence: `no_consent`, `not_approved`, `invalid_message`, `blank_response`, `ambiguous_preference`, `over_length`, then `duplicate_content`.

The authoritative group split is in `prompt_group_assignments.csv`; do not split a prompt group across train and eval. Preserve each accepted row's `pair_id`, `prompt_group_id`, `prompt`, `chosen`, and `rejected` so a reviewer can trace it back to the export.

## Training settings

Use the local model at `/root/data/model/fictional-tiny-instruct` with DPO and LoRA. The run settings are: two processes, two epochs, learning rate `5e-6`, beta `0.1`, maximum length `1024`, maximum prompt length `384`, evaluation every 25 steps, seed `7319`, bf16 enabled, LoRA rank `16`, LoRA alpha `32`, and unused-column removal disabled. Per-device train batch size must be no more than the hardware limit; choose a positive gradient accumulation value so

`per_device_train_batch_size × gradient_accumulation_steps × num_processes = required_effective_global_batch_size`.

Use step-based evaluation, a local checkpoint directory inside the bundle, no Hub push, and no remote experiment reporter.

## Bundle contract

Create `/root/results/dpo_run/` containing:

- `train.jsonl` and `eval.jsonl`: eligible conversational records assigned to each split.
- `dpo_config.yaml`: the complete DPO configuration. It must identify the prepared files through `train_dataset_path` and `eval_dataset_path` so the bundled preflight runner can validate them.
- `launch.sh`: an executable, location-independent script that invokes `trl dpo --config` for this bundle and returns the command's status.
- `preflight_report.json`: source/included/excluded totals, included split counts, exclusion counts by reason, one `{pair_id, reason}` entry for every exclusion, selected method, effective batch size, GPU/process count, a concise decision summary, the configuration rationale, and actionable residual risks. State clearly that the local launch is a configuration/data preflight rather than completed model training.

Before handoff, run `launch.sh` locally. The installed `trl` command is an offline preflight implementation: it validates the DPO command, local paths, data shape, and resource arithmetic without loading model weights or training.
