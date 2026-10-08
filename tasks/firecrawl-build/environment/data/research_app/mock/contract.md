# Offline web-data service contract

The mock preserves the request/response objects used by the hosted integration. All requests require `Authorization: Bearer <non-empty value>` and JSON content.

## `POST /v1/search`

Request: `{"query": "...", "limit": 5}`. The mock requires `limit` to be exactly `5` so discovery has enough candidates for filtering. Success is HTTP 200:

```json
{"success": true, "data": [{"title": "...", "url": "...", "description": "..."}]}
```

Search results are already relevance-ranked. Preserve this ordering when selecting usable items.

## `POST /v1/scrape`

Request: `{"url": "...", "formats": ["markdown"]}`. Success is HTTP 200:

```json
{"success": true, "data": {"markdown": "...", "metadata": {"title": "...", "sourceURL": "..."}}}
```

A page-specific failure may be HTTP 422 with `{"success": false, "error": "..."}`. Treat non-2xx responses, malformed JSON, and unsuccessful envelopes as failures of that page only. Error text returned to the CLI must not include credentials.

## Mock runner

For a manual smoke test from the project directory:

```bash
python3 mock/mock_server.py --index mock/search_index.json --port 8765
```

Set `FIRECRAWL_API_URL=http://127.0.0.1:8765` and a placeholder API key in the process environment. The server writes a JSON request log when `MOCK_LOG_PATH` is set.
