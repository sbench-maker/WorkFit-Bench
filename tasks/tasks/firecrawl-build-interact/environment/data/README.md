# Local catalog integration fixture

`starter/firecrawl_mock.py` is an offline stand-in for the product's Firecrawl client. It exposes `scrape(url)` and `interact(session_id, actions)`. A scrape returns the initial page and a browser session. Interactions accept `fill`, `click`, and `extract` action objects; filters and pagination are stateful and must stay in that session.

Complete `starter/collector.py` without changing its CLI: `python3 collector.py --case CASE_DIR --output OUTPUT_JSON`. The output is a JSON array of every non-deprecated record in the requested category, sorted by `id`. The mock writes a sibling `*.trace.json` file recording calls, session IDs, and actions. Do not read `site_data.json` directly from the collector; it represents the page backend, while the mock client is the integration boundary.

Both cases are deterministic. The primary case is the requested production snapshot; the regression case exists to check that the integration is reusable rather than tailored to one catalog page.
