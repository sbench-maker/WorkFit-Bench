# Offline issue-sync base

This directory contains a deterministic, Airtable-compatible REST sandbox for base `appDevTriage01`, table `tblIssues01` (`Issues`). It uses no authentication and accepts only loopback requests.

Start it before reading or mutating records:

```bash
python3 /root/data/airtable_mock.py \
  --state /root/results/base_state.json \
  --audit /root/results/api_activity.jsonl \
  --port 8765 &
```

The API root is `http://127.0.0.1:8765/v0`. The server copies the frozen initial base to the state path on first start and preserves that state if restarted. It writes one JSON line per request to the audit path.

Supported operations mirror the relevant Airtable REST shapes:

- `GET /v0/meta/bases/appDevTriage01/tables` returns table and field schema.
- `GET /v0/appDevTriage01/Issues?pageSize=100` lists records. Pages are capped at 100; follow the returned `offset` until it is absent.
- `GET /v0/appDevTriage01/Issues/{record_id}` gets one record.
- `PATCH /v0/appDevTriage01/Issues` accepts an Airtable batch upsert body. Each request may contain at most 10 records and must use `performUpsert.fieldsToMergeOn: ["External ID"]`.

The mock returns Airtable-style JSON errors and HTTP statuses. Use the schema response rather than assuming select options or field types. Read `sync_policy.md` before constructing writes.
