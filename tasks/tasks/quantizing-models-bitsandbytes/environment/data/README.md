# Quantized deployment planning snapshot

This directory is a fictional, frozen planning export. `deployment_requests.csv`
joins to `models.csv` by `model_id` and to `gpu_inventory.csv` by `gpu_id`.
`planning_policy.json` is the operations policy for this planning run.

## Decision rules

For each request, evaluate the modes in `mode_priority` order and select the
first mode that is supported, stays within `max_accuracy_loss_pct`, and is
deployable. Quantized modes also require a bitsandbytes-compatible GPU.

Weight memory is `parameters_b * weight_gb_per_billion_parameters[mode]`.
The GPU space available for weights is:

`vram_gb - reserved_vram_gb - nonweight_gpu_gb`

A mode is a native placement when all weight memory fits in that space. If it
does not fit, CPU offload is allowed only when the request permits it, its
latency class is listed in the policy, the GPU can retain at least the policy's
minimum weight fraction, and the spill is no larger than the GPU profile's CPU
offload capacity. Equality satisfies every limit. Reject the request when no
mode is deployable.

## Output contract

Write a JSON object containing one plan per request plus a summary. Each plan
must keep `request_id`, `model_id`, and `gpu_id` traceable and report:

- accepted/rejected status, selected mode, and native/CPU-offload placement;
- estimated total weight memory, weight held on GPU, CPU spill, accuracy loss,
  and GPU space available for weights;
- quantization kwargs (or null for FP16/rejected work), model-loading kwargs,
  and a concise operator note.

For 4-bit plans, the quantization kwargs must represent NF4 with double
quantization. The compute dtype is BF16 only where the GPU supports it,
otherwise FP16. For 8-bit plans, use the policy-selected outlier threshold,
INT8 weight storage, and the model's listed skipped modules. Model-loading
kwargs use automatic device placement. CPU-offloaded plans also provide GPU and
CPU `max_memory` values, an offload folder inside `/root/results/offload/`, and
state-dict offload.

The summary must reconcile accepted/rejected totals, counts by mode and
placement, and aggregate estimated weight, GPU-weight, and CPU-offload memory.
Use two decimal places for reported numeric values. JSON key names and ordering
are not otherwise fixed.
