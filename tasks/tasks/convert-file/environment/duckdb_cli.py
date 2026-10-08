#!/usr/bin/env python3
"""Small offline-compatible `duckdb -c` command backed by the pinned package."""

from __future__ import annotations

import argparse
import re
import sys

import duckdb


def main() -> int:
    parser = argparse.ArgumentParser(prog="duckdb")
    parser.add_argument("database", nargs="?", default=":memory:")
    parser.add_argument("-c", "--command", required=True)
    args = parser.parse_args()
    try:
        # DuckDB documents COMPRESSION for Parquet; accept the source workflow's
        # equivalent CODEC spelling so its command remains portable offline.
        command = re.sub(
            r"\bCODEC\s+((?:'[^']+')|(?:[A-Za-z0-9_]+))",
            r"COMPRESSION \1",
            args.command,
            flags=re.IGNORECASE,
        )
        connection = duckdb.connect(args.database)
        result = connection.execute(command)
        if result.description:
            rows = result.fetchall()
            if rows:
                print("\t".join(str(value) for value in rows[0]))
                for row in rows[1:]:
                    print("\t".join(str(value) for value in row))
        connection.close()
        return 0
    except Exception as exc:  # DuckDB formats the actionable parse/conversion error.
        print(f"duckdb: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
