# Trailbook Field Notes

This fictional Expo SDK 55 prototype keeps a small offline trail journal. Home shows every note, Saved shows favorites, Search filters the same dataset, and selecting a card opens `/notes/:id`.

## Existing behavior to preserve

- Home displays notes newest-first.
- Saved contains only records with `saved: true`.
- Search is case-insensitive, ignores surrounding whitespace, and matches title, body, author, or tags.
- An empty query shows all notes; a non-empty miss shows a useful empty state.
- Unknown note IDs show a not-found message with a route back to Home.

Run `python3 scripts/validate-data.py` to check the frozen local dataset. The package manifest documents the intended SDK; dependencies are not vendored in this offline fixture.
