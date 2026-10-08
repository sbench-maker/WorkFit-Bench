# Northstar Relay frozen site snapshot

This is a deterministic, fictional export prepared for an internal AI-search visibility audit. It is the complete evidence set for the assignment; no live lookup or external corroboration is expected.

- `site_profile.json` defines the snapshot date, priority-page scope, and product context.
- `site_pages.jsonl` is the crawl inventory. `server_word_count` is visible in the initial HTML; `rendered_word_count` is visible after client-side rendering.
- `passages.jsonl` contains the candidate passages extracted from priority pages. Bracketed `EVD-*` tokens refer to `evidence_register.csv`.
- `crawler_access.csv` records the effective result of applying `robots.txt` to each priority path and named crawler.
- `query_observations.csv` is a frozen set of platform/query observations; `cited=1` means this fictional site appeared as a cited source.
- `brand_mentions.csv` records candidate brand mentions. Only rows with `confirmed=1` refer to this fictional company.
- `llms.txt` is the file found at the site root in the snapshot.
- `scoring_model.json` is the marketing team's agreed, deterministic readiness model. Scores are rounded to the nearest whole number only after each platform formula is evaluated; the overall score is the rounded arithmetic mean of the three unrounded platform scores.

All paths are site-relative identifiers, not claims about public webpages. Empty values mean the crawl did not expose that evidence.
