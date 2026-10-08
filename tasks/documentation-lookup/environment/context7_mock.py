#!/usr/bin/env python3
"""Small deterministic offline mock of Context7's resolve/query contract."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


VERSION = "1.0.0"
DATA_DIR = Path(os.environ.get("SKILLSBENCH_DATA_DIR", "/root/data")).resolve()
TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokens(value: str) -> list[str]:
    return TOKEN_RE.findall(value.lower())


def state_path() -> Path:
    return Path("/tmp") / f"context7-mock-state-{os.getuid()}.json"


def read_catalog() -> list[dict]:
    return json.loads((DATA_DIR / "library_catalog.json").read_text(encoding="utf-8"))


def resolve(args: argparse.Namespace) -> int:
    needle = f"{args.library_name} {args.query}"
    query_tokens = set(tokens(needle))
    exact_name = " ".join(tokens(args.library_name))
    version_tokens = set(re.findall(r"\bv?\d+(?:\.\d+)+\b", needle.lower()))
    rows = []
    for item in read_catalog():
        haystack = f"{item['name']} {item['library_id']} {item['description']} {item['version']}"
        hay_tokens = set(tokens(haystack))
        overlap = len(query_tokens & hay_tokens)
        score = overlap * 12 + float(item["benchmark_score"]) / 10
        if exact_name and exact_name == " ".join(tokens(item["name"])):
            score += 80
        if item.get("official"):
            score += 6
        if item.get("source_reputation") == "High":
            score += 4
        if any(version.lstrip("v") in item["version"] for version in version_tokens):
            score += 35
        row = dict(item)
        row["resolution_score"] = round(score, 3)
        rows.append(row)
    rows.sort(key=lambda row: (-row["resolution_score"], -row["benchmark_score"], row["library_id"]))
    selected = rows[: args.limit]
    state_path().write_text(
        json.dumps({"resolved_ids": [row["library_id"] for row in selected], "query_count": 0}),
        encoding="utf-8",
    )
    print(json.dumps({"results": selected}, ensure_ascii=False, indent=2))
    return 0


def query(args: argparse.Namespace) -> int:
    path = state_path()
    if not path.is_file():
        raise SystemExit("resolve-library-id must be called before query-docs")
    state = json.loads(path.read_text(encoding="utf-8"))
    if args.library_id not in state.get("resolved_ids", []):
        raise SystemExit("library ID was not returned by the preceding resolution")
    if int(state.get("query_count", 0)) >= 3:
        raise SystemExit("documentation query limit reached for this resolution")

    query_tokens = set(tokens(args.query))
    matches = []
    with (DATA_DIR / "document_chunks.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            if item["library_id"] != args.library_id:
                continue
            title_tokens = set(tokens(f"{item['title']} {' '.join(item['tags'])}"))
            body_tokens = set(tokens(item["content"]))
            score = len(query_tokens & title_tokens) * 5 + len(query_tokens & body_tokens)
            row = dict(item)
            row["relevance_score"] = score
            matches.append(row)
    matches.sort(key=lambda row: (-row["relevance_score"], row["chunk_id"]))
    state["query_count"] = int(state.get("query_count", 0)) + 1
    path.write_text(json.dumps(state), encoding="utf-8")
    print(json.dumps({"library_id": args.library_id, "results": matches[: args.limit]}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="context7-mock")
    parser.add_argument("--version", action="version", version=VERSION)
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolver = subparsers.add_parser("resolve-library-id")
    resolver.add_argument("--library-name", required=True)
    resolver.add_argument("--query", required=True)
    resolver.add_argument("--limit", type=int, default=8, choices=range(1, 11))
    resolver.set_defaults(func=resolve)

    docs = subparsers.add_parser("query-docs")
    docs.add_argument("--library-id", required=True)
    docs.add_argument("--query", required=True)
    docs.add_argument("--limit", type=int, default=6, choices=range(1, 11))
    docs.set_defaults(func=query)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
