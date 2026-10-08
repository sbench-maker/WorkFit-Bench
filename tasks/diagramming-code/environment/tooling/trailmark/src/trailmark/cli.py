"""Command-line summary interface for the offline fixture runtime."""

from __future__ import annotations

import argparse
import json
from typing import List, Optional

from trailmark.parse import detect_languages
from trailmark.query.api import QueryEngine


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="trailmark")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("target")
    analyze.add_argument("--language", default="auto")
    analyze.add_argument("--summary", action="store_true")
    analyze.add_argument("--complexity", type=int)
    entrypoints = subparsers.add_parser("entrypoints")
    entrypoints.add_argument("target")
    entrypoints.add_argument("--language", default="auto")
    args = parser.parse_args(argv)
    engine = QueryEngine.from_directory(args.target, language=args.language)
    if args.command == "entrypoints":
        print(json.dumps(engine.attack_surface(), indent=2))
        return 0
    if args.complexity is not None:
        print(json.dumps(engine.complexity_hotspots(args.complexity), indent=2))
    elif args.summary:
        summary = engine.summary()
        print("Languages: " + ", ".join(detect_languages(args.target)))
        print(f"Entrypoints: {summary['entrypoints']}")
        dependencies = sorted({target for _, target in engine.graph.module_edges()})
        print("Dependencies: " + ", ".join(dependencies))
        print(json.dumps(summary, indent=2))
    else:
        print(json.dumps(engine.to_json(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
