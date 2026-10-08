#!/usr/bin/env python3
"""Offline-compatible stand-in for the Burp project parser CLI.

It accepts the Java/Burp argument shape used by the bundled wrapper and exposes
the same auditItems, proxyHistory/siteMap component, and regex-search objects.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path


VERSION = "offline-burp-project-parser 1.0.0"


def emit(row: dict) -> None:
    print(json.dumps(row, ensure_ascii=False, separators=(",", ":")))


def project_and_flags(argv: list[str]) -> tuple[Path, list[str]]:
    project: Path | None = None
    flags: list[str] = []
    skip_next = False
    for index, arg in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        if arg in {"--version", "-version"}:
            print(VERSION)
            raise SystemExit(0)
        if arg == "-jar":
            skip_next = True
            continue
        if arg.startswith("-D") or arg.endswith(".jar"):
            continue
        if arg.startswith("--project-file="):
            project = Path(arg.split("=", 1)[1])
        elif arg == "--project-file" and index + 1 < len(argv):
            project = Path(argv[index + 1])
            skip_next = True
        else:
            flags.append(arg)
    if project is None:
        raise SystemExit("missing --project-file")
    return project, flags


def traffic_object(row: sqlite3.Row, component: str | None = None) -> dict:
    request = {"method": row["method"], "url": row["url"], "headers": row["request_headers"], "body": row["request_body"]}
    response = {"status": row["status"], "headers": row["response_headers"], "body": row["response_body"]}
    if component is None:
        return {"id": row["record_id"], "url": row["url"], "request": request, "response": response, "notes": row["notes"]}
    side, field = component.split(".", 1)
    payload = request if side == "request" else response
    return {"id": row["record_id"], "url": row["url"], side: {"url": row["url"], field: payload[field]}}


def parse_regex(flag: str, name: str) -> re.Pattern[str] | None:
    match = re.fullmatch(rf"{name}=(?:'(?P<sq>.*)'|\"(?P<dq>.*)\")", flag)
    if not match:
        return None
    raw = match.group("sq") if match.group("sq") is not None else match.group("dq")
    try:
        return re.compile(raw, re.DOTALL)
    except re.error as exc:
        raise SystemExit(f"invalid regex: {exc}")


def main() -> int:
    project, flags = project_and_flags(sys.argv[1:])
    if not project.is_file():
        raise SystemExit(f"project file not found: {project}")
    connection = sqlite3.connect(f"file:{project}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        for flag in flags:
            if flag == "auditItems":
                query = "SELECT * FROM audit_items ORDER BY finding_id"
                for row in connection.execute(query):
                    emit(dict(row))
                continue

            if flag == "projectInfo":
                emit({row["key"]: row["value"] for row in connection.execute("SELECT key, value FROM project_metadata ORDER BY key")})
                continue

            component_match = re.fullmatch(r"(proxyHistory|siteMap)(?:\.(request|response)\.(headers|body))?", flag)
            if component_match:
                source = "proxy" if component_match.group(1) == "proxyHistory" else "siteMap"
                component = None
                if component_match.group(2):
                    component = f"{component_match.group(2)}.{component_match.group(3)}"
                for row in connection.execute("SELECT * FROM traffic WHERE source = ? ORDER BY record_id", (source,)):
                    emit(traffic_object(row, component))
                continue

            header_pattern = parse_regex(flag, "responseHeader")
            if header_pattern is not None:
                for row in connection.execute("SELECT * FROM traffic WHERE source = 'proxy' ORDER BY record_id"):
                    if header_pattern.search(row["response_headers"]):
                        emit({"id": row["record_id"], "url": row["url"], "status": row["status"], "header": row["response_headers"]})
                continue

            body_pattern = parse_regex(flag, "responseBody")
            if body_pattern is not None:
                for row in connection.execute("SELECT * FROM traffic WHERE source = 'proxy' ORDER BY record_id"):
                    if body_pattern.search(row["response_body"]):
                        emit({"id": row["record_id"], "url": row["url"], "status": row["status"], "body": row["response_body"], "notes": row["notes"]})
                continue

            raise SystemExit(f"unsupported parser flag: {flag}")
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
