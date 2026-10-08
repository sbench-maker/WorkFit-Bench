#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def main() -> None:
    root = Path("/root/data")
    files = []
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
    result = {"root": str(root), "complete": True, "files": files, "limitations": []}
    Path("/logs/verifier/input_completeness.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
