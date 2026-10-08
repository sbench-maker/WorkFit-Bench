# Lumen Research Service

This existing Python service turns a topic query into a ranked, hydrated shortlist for an editorial workflow. Complete the stub in `src/research_app/research.py` without changing the command-line response contract documented below.

## Run

```bash
PYTHONPATH=src python3 -m research_app.cli "battery recycling"
```

The command prints one JSON object:

```json
{
  "query": "battery recycling",
  "results": [
    {
      "title": "A result title",
      "url": "https://fictional.test/page",
      "snippet": "Search-result summary",
      "content": "Full page markdown, or null when hydration fails",
      "error": null
    }
  ]
}
```

`results` contains at most three usable search results in the order supplied by search. A usable result has a non-empty HTTP(S) URL. If scraping one selected page fails, retain its discovery metadata, set `content` to `null`, put a concise non-sensitive message in `error`, and continue hydrating the other selected pages. On success, `error` is `null`.

## Runtime configuration

- `FIRECRAWL_API_KEY` is required and must be sent as `Authorization: Bearer <value>`.
- `FIRECRAWL_API_URL` optionally overrides the hosted base URL. Ignore a trailing slash when constructing paths.
- Requests and responses follow `mock/contract.md`. Use the existing standard-library stack; no install step is available at runtime.

The local mock server is for offline development and verification. It is started separately and exposes its base URL through `FIRECRAWL_API_URL`; integration code must not import its implementation or read its index directly.
