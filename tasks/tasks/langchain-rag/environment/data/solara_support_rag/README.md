# Solara support RAG starter

This directory is a fictional, offline fixture for a small support knowledge
assistant. Complete `rag_cli.py`, then copy the runnable project to
`/root/results/solara_support_rag/` and build its default persistent index at
`/root/results/solara_support_rag/index/`.

## Inputs

- `knowledge_base/*.md` contains versioned operations manuals. Each file has
  front matter and ten `## section-slug — title` sections.
- `section_catalog.csv` has one row per section. `source_id` is the canonical
  citation and the five scope fields are `product`, `release`, `region`,
  `audience`, and `status`.
- `batch_queries.jsonl` contains support questions, exact metadata filters, and
  a requested `top_k`.

All data is local and fictional. The finished program must not require a model
service, package download, or network connection.

## Command-line contract

The starter exposes two subcommands. Keep these arguments usable:

```text
python3 rag_cli.py build --corpus DIR --catalog CSV --index DIR
python3 rag_cli.py answer --index DIR --queries JSONL --output JSON
```

`build` must load the Markdown sections, associate catalog metadata, split
long text where needed, derive deterministic local retrieval vectors, and save
a self-contained index. `answer` must load that saved index without consulting
the original corpus or catalog, apply every query's exact metadata filters,
retrieve up to `top_k` relevant chunks, and produce one grounded response per
query. Re-running either command with the same inputs should be deterministic.

The output JSON may be a top-level list or an object containing an `answers`,
`results`, or `responses` list. Each response needs the query ID, an answer,
status (`answered` or `insufficient`), and citations containing canonical
`source_id` values. Equivalent field names and additional retrieval diagnostics
are welcome. If no active section matches all supplied filters, return an
`insufficient` response with no citation instead of borrowing from another
scope or a retired manual.

For this corpus, the sentence beginning `Operational directive:` is the
authoritative answer-bearing statement. The response may quote or faithfully
paraphrase it, but every material instruction must be supported by the cited
eligible section.

