#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    root = Path("/root/data")
    files = []
    if root.is_dir():
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            files.append({
                "path": str(path),
                "bytes": path.stat().st_size,
                "available": True,
                "truncated": False,
            })
    payload = {
        "schema_version": "1.0",
        "root": str(root),
        "complete": root.is_dir() and bool(files),
        "files": files,
        "limitations": [] if files else ["No local task inputs were available to the verifier."],
    }
    out = Path("/logs/verifier/input_completeness.json")
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
