# Offline quantization workspace

This directory contains a fictional decoder checkpoint and the deployment contract:

- `model_manifest.json` describes every matrix in the checkpoint.
- `checkpoint_weights.jsonl` contains one matrix row per line (`layer`, `row`, `values`).
- `deployment_request.json` fixes the target hardware, quality limits, supported backends, precision choices, protected modules, and optimization objective.
- `hqq_runtime.py` is the installed offline quantization runtime for this snapshot. It uses no calibration examples or network resources.

## Runtime API

Import `hqq_runtime` to inspect `candidate_table(layer)` or `evaluate_layer(layer, nbits, group_size)`. Build a bundle with:

```bash
python3 /root/data/hqq_runtime.py --config /path/to/config.json --output-dir /root/results
```

The config accepts `backend`, `axis`, `calibration_data_used`, and `layer_configs`. Every manifest layer must appear. Protected modules use `null` or `"fp16"`; other layers use `{ "nbits": 4, "group_size": 64 }`. A `deployment_handoff` string may be included.

The runtime writes `output.json` and `quantized_weights.jsonl`. The manifest records the selected configuration, reconstruction RMSE, packed-size accounting, and artifact location. A valid deployment must meet every per-layer RMSE limit and the package byte ceiling. Among valid packages, the request defines “smallest” by total packed bytes, then overall RMSE. Partial final groups are supported because each matrix has 130 columns.
