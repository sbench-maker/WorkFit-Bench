#!/usr/bin/env python3
"""Minimal offline-compatible `duckdb -c` command backed by the pinned package."""

from __future__ import annotations

import argparse
import sys

import duckdb


def main() -> int:
    parser = argparse.ArgumentParser(prog="duckdb")
    parser.add_argument("database", nargs="?", default=":memory:")
    parser.add_argument("-c", "--command")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args()
    if args.version:
        print(duckdb.__version__)
        return 0
    if not args.command:
        parser.error("the following arguments are required: -c/--command")
    try:
        connection = duckdb.connect(args.database)
        result = connection.execute(args.command)
        if result.description:
            names = [column[0] for column in result.description]
            print("\t".join(names))
            for row in result.fetchall():
                print("\t".join("" if value is None else str(value) for value in row))
        connection.close()
        return 0
    except Exception as exc:
        print(f"duckdb: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
