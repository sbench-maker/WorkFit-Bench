#!/usr/bin/env python3
"""Offline DuckDB CLI subset used by the bundled attachment workflow."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import duckdb


def split_sql(script: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    single = False
    double = False
    line_comment = False
    index = 0
    while index < len(script):
        char = script[index]
        nxt = script[index + 1] if index + 1 < len(script) else ""
        if line_comment:
            current.append(char)
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if not single and not double and char == "-" and nxt == "-":
            current.extend([char, nxt])
            line_comment = True
            index += 2
            continue
        if char == "'" and not double:
            current.append(char)
            if single and nxt == "'":
                current.append(nxt)
                index += 2
                continue
            single = not single
        elif char == '"' and not single:
            current.append(char)
            if double and nxt == '"':
                current.append(nxt)
                index += 2
                continue
            double = not double
        elif char == ";" and not single and not double:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
        index += 1
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def emit_result(result: duckdb.DuckDBPyConnection, csv_mode: bool) -> None:
    if not result.description:
        return
    rows = result.fetchall()
    header = [item[0] for item in result.description]
    if csv_mode:
        writer = csv.writer(sys.stdout, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    else:
        print("\t".join(header))
        for row in rows:
            print("\t".join("" if value is None else str(value) for value in row))


def main() -> int:
    parser = argparse.ArgumentParser(prog="duckdb")
    parser.add_argument("database", nargs="?", default=":memory:")
    parser.add_argument("-c", "--command", required=True)
    parser.add_argument("-init", dest="init_file")
    parser.add_argument("-csv", action="store_true", dest="csv_mode")
    args = parser.parse_args()
    try:
        connection = duckdb.connect(args.database)
        scripts = []
        if args.init_file:
            scripts.append(Path(args.init_file).read_text(encoding="utf-8"))
        scripts.append(args.command)
        for script in scripts:
            for statement in split_sql(script):
                emit_result(connection.execute(statement), args.csv_mode)
        connection.close()
        return 0
    except Exception as exc:
        print(f"duckdb: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
