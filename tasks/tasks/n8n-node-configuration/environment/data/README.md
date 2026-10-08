# Offline n8n configuration fixture

This directory contains a draft workflow export, the coordinator's change brief, a versioned node catalog, and 240 fictional participant-submission examples. No network service or credential is needed.

Use the local catalog and validator like the corresponding discovery/validation loop:

```bash
python3 /root/data/n8n_offline.py get_node n8n-nodes-base.httpRequest
python3 /root/data/n8n_offline.py get_node n8n-nodes-base.httpRequest --search body
python3 /root/data/n8n_offline.py validate_workflow /root/results/configured_workflow.json
```

`get_node` defaults to standard detail. `--detail full` returns the complete frozen catalog entry; `--search` filters its properties and dependency notes. Validation is deterministic and reads only local files.
