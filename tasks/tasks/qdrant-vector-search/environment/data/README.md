# Offline retrieval fixture

All organizations, products, articles, and vectors in this directory are fictional and locally constructed.

## Inputs

- `collection_spec.json` defines the collection name, named dense vector, cosine distance, vector size, and payload indexes.
- `knowledge_points.jsonl` contains one JSON object per point: `point_id`, a 12-dimensional `vector`, and a JSON `payload`.
- `query_requests.json` contains batch requests with `query_id`, `query_vector`, `limit`, and a Qdrant-style `filter` object. Apply the full filter before nearest-neighbor ranking. Returning fewer than `limit` hits is correct when fewer points qualify.

Every returned hit must identify the source point, include its cosine similarity score, and include the source payload so Support can audit tenant and effective-date isolation. Do not return stored vectors.

## Deliverable contract

`/root/results/output.json` should be a JSON document containing one result group per input `query_id`; each group contains an ordered hit list. Equivalent labels or nesting are acceptable if the query ID, point ID, score, and payload are unambiguous.

`/root/results/retriever.py` must be independently repeatable with:

```bash
python3 /root/results/retriever.py --data-dir /root/data --output /root/results/output.json
```

The script must rebuild a fresh embedded/local collection from the supplied files and must not require a server, network, or credentials.
