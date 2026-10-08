#!/usr/bin/env python3
"""Starter command-line entry point for the offline support RAG prototype."""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build or query the local Solara support index")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="build a persistent local index")
    build.add_argument("--corpus", type=Path, required=True)
    build.add_argument("--catalog", type=Path, required=True)
    build.add_argument("--index", type=Path, required=True)

    answer = subparsers.add_parser("answer", help="answer a JSONL batch from a saved index")
    answer.add_argument("--index", type=Path, required=True)
    answer.add_argument("--queries", type=Path, required=True)
    answer.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    parser.error(f"the {args.command!r} workflow is not implemented yet")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
