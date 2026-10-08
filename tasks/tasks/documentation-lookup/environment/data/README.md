# Frozen Context7-style snapshot

This directory is a deterministic, fictional documentation snapshot for offline use. It contains a resolver catalog and versioned documentation chunks; it does not represent observations from an external service.

The installed `context7-mock` command preserves the two-stage lookup contract:

```text
context7-mock resolve-library-id --library-name "library name" --query "full question"
context7-mock query-docs --library-id "/org/project/version" --query "focused question" --limit 6
```

`resolve-library-id` returns ranked candidates with names, versions, benchmark scores, source reputation, and official-source flags. `query-docs` accepts only an ID returned by the preceding resolution step for the current user and returns ranked section records from `document_chunks.jsonl`. Up to three documentation queries are allowed after each resolution. `context7-mock --version` prints the mock version.

The fixture files are:

- `library_catalog.json`: resolver candidates.
- `document_chunks.jsonl`: documentation sections keyed by `library_id` and `chunk_id`.
- `snapshot_manifest.json`: completeness and construction metadata.

No command performs network access, and no credentials are needed. Treat example environment-variable names as placeholders; never put a credential value into the answer.
