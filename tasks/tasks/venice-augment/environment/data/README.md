# Frozen augmentation service

This directory contains a fictional release-candidate manifest and a deterministic 240-page web snapshot. Nothing here is a real observation or an external source.

Start the local service in the background:

```bash
python3 /root/data/augment_mock.py --port 8765 >/tmp/orchid-augment.log 2>&1 &
```

It exposes the same request and response objects used by the augmentation helpers, without authentication or network access:

- `POST http://127.0.0.1:8765/api/v1/augment/search` with `{"query":"...","limit":10,"search_provider":"brave"}`
- `POST http://127.0.0.1:8765/api/v1/augment/scrape` with `{"url":"https://..."}`

Search results contain title, URL, snippet content, and date. Scrape responses contain URL, markdown content, and format. Search snippets are discovery aids; the complete scraped body is the evidence. The mock returns the normal `INVALID_REQUEST`, `BLOCKED_SOURCE`, and `UPSTREAM_FAILURE` error shapes for applicable requests.
