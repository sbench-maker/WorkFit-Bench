# Offline tuning control plane

Use `python3 /root/data/mock_agent_platform.py --help` to inspect the local control-plane commands. Initialize a state file, verify the run-prefix bucket with `storage-ls`, upload both JSONL partitions with `storage-cp`, then submit a request and monitor its returned job ID.

The request object uses these fields: `project`, `location`, `base_model`, `train_dataset`, `validation_dataset`, `output_uri`, `epochs`, `learning_rate`, `tuning_mode`, and `adapter_size`. Use distinct object URIs under the confirmed run prefix, and use `<run-prefix>/output` for `output_uri`. The mock rejects inaccessible storage, unuploaded datasets, or an unsupported configuration; it never contacts a network service.
