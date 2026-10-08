# Offline Remotion documentation mirror

This directory is a deterministic, offline fixture. It is not a live documentation export. `cases.json` contains the support queue, `search_index.json` contains Algolia-shaped section records, and `pages/` contains the Markdown snapshots identified by the search hits.

Use the mirror with:

```bash
python3 /root/data/docs_mirror.py search "sequence local frame" --limit 10
python3 /root/data/docs_mirror.py fetch https://www.remotion.dev/docs/sequence.md
```

`search` returns `{"results": [{"hits": [...]}]}` with hierarchy and canonical URL fields. `fetch` accepts a canonical URL with or without the `.md` suffix and emits its Markdown snapshot.

Write `/root/results/output.json` as UTF-8 JSON in this shape:

```json
{
  "snapshot_id": "the snapshot ID from the mirror",
  "cases": [
    {
      "case_id": "RMT-000",
      "answer": "Concise documented guidance",
      "sources": ["https://www.remotion.dev/docs/canonical-page"],
      "caveats": ["Only material version or environment limitations"]
    }
  ]
}
```

Include each queued case once. Use the smallest set of canonical documentation pages that supports the answer; do not cite search records or fabricate URLs.
