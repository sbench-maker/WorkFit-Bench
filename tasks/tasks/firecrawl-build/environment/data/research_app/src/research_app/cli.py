from __future__ import annotations

import json
import sys

from .research import research_topic


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        print("usage: python -m research_app.cli <query>", file=sys.stderr)
        return 2
    try:
        payload = research_topic(sys.argv[1])
    except Exception as exc:
        print(f"research failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
