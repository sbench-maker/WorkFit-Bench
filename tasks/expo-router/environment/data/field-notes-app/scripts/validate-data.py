#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
records = json.loads((ROOT / "data" / "notes.json").read_text(encoding="utf-8"))
assert len(records) == 24, "expected 24 frozen note records"
assert len({row["id"] for row in records}) == len(records), "note IDs must be unique"
assert all(row["id"].startswith("fn-") for row in records), "invalid note ID"
assert all(date.fromisoformat(row["observedAt"]) for row in records), "invalid observation date"
assert all(isinstance(row["tags"], list) and row["tags"] for row in records), "tags must be non-empty"
assert any(row["saved"] for row in records) and any(not row["saved"] for row in records)
print(f"validated {len(records)} fictional field notes")
