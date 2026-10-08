#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def inventory(root: Path) -> list[dict[str, object]]:
    files = []
    if not root.exists():
        return files
    for path in sorted(root.rglob("*")):
        if path.is_file():
            payload = path.read_bytes()
            files.append(
                {
                    "path": str(path.relative_to(root)),
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "truncated": False,
                }
            )
    return files


def main() -> None:
    data_root = Path("/root/data")
    results_root = Path("/root/results")
    payload = {
        "complete": data_root.is_dir() and results_root.is_dir(),
        "inputs": inventory(data_root),
        "submission": inventory(results_root),
        "limitations": [],
    }
    Path("/logs/verifier/input_completeness.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
