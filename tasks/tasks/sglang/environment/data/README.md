# Offline routing fixture

This directory contains fictional support tickets and a frozen routing policy. `tickets.jsonl` is the primary batch. `holdout_tickets.jsonl` is a smaller offline rerun batch used to show that the implementation is reusable. Apply `routing_policy.json` literally: compare the combined subject and body case-insensitively, select the first rule containing any listed phrase, and otherwise use `fallback`.

The installed `sglang` module is a deterministic offline compatibility runtime. It exposes `function`, `gen`, and `run_batch` with the same program/bind/state shape used by the structured-generation examples in the injected documentation. Generation prompts must contain a shared `POLICY_JSON:` object before a unique `TICKET_JSON:` object. Call `gen(..., json_schema=...)`; each state value is returned as JSON text. After `run_batch`, call `get_last_batch_metrics()` for observed constraint and prefix-cache metrics. The runtime accepts no network calls and no model downloads.

Create a reusable `/root/results/router.py` with this command-line interface:

```text
python3 /root/results/router.py --input TICKETS.jsonl --policy routing_policy.json --contract output_contract.json --output OUTPUT.json
```

The artifact shape and fields are in `output_contract.json`. The routing `reason` should identify the decisive ticket signal in a short operator-facing sentence rather than echoing the whole ticket. All reported runtime metrics must be taken from the completed batch.
