#!/usr/bin/env python3
"""Read-only offline stand-in for the Workspace views named by the bundled skill."""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data")).resolve()


def read_csv(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def emit(payload: object) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def workflow(name: str) -> int:
    if name == "+standup-report":
        rows = [row for row in read_jsonl("chat_messages.jsonl") if row["thread_id"].startswith("STANDUP-")]
        return emit({"offline": True, "workflow": name, "messages": rows})
    if name == "+email-to-task":
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in read_jsonl("email_messages.jsonl"):
            if "automated" not in row["labels"]:
                grouped[row["thread_id"]].append(row)
        return emit({"offline": True, "workflow": name, "threads": grouped})
    if name == "+meeting-prep":
        rows = sorted(read_csv("calendar_events.csv"), key=lambda row: (row["owner_id"], row["start_at"]))
        return emit({"offline": True, "workflow": name, "events": rows})
    if name == "+weekly-digest":
        meta = json.loads((DATA / "snapshot_meta.json").read_text(encoding="utf-8"))
        return emit({
            "offline": True,
            "workflow": name,
            "snapshot": meta,
            "views": [
                "gws workflow +standup-report",
                "gws workflow +email-to-task",
                "gws workflow +meeting-prep",
                "gws calendar +agenda --week --format table",
            ],
            "note": "This mock exposes frozen source objects; write the reviewable proposal to /root/results/output.json.",
        })
    print(f"offline gws: unsupported workflow {name}", file=sys.stderr)
    return 2


def agenda() -> int:
    roster = {row["user_id"]: row["name"] for row in read_csv("roster.csv")}
    rows = sorted(read_csv("calendar_events.csv"), key=lambda row: (row["start_at"], row["owner_id"], row["event_id"]))
    print("EVENT_ID\tOWNER\tSTART\tEND\tKIND\tTITLE")
    for row in rows:
        print("\t".join([row["event_id"], roster.get(row["owner_id"], row["owner_id"]), row["start_at"], row["end_at"], row["kind"], row["title"]]))
    return 0


def main() -> int:
    args = [arg for arg in sys.argv[1:] if arg != "--sanitize"]
    if not args or args in (["--help"], ["help"]):
        print("offline gws mock: workflow <name> | calendar +agenda --week --format table")
        return 0
    if args == ["--version"]:
        print("gws offline-mock 1.0.0")
        return 0
    if len(args) >= 2 and args[0] == "workflow":
        return workflow(args[1])
    if len(args) >= 2 and args[0] == "calendar" and args[1] == "+agenda":
        return agenda()
    if args[:2] in (["chat", "spaces"], ["sheets", "+append"]):
        print("offline gws is read-only; record proposed writes in /root/results/output.json", file=sys.stderr)
        return 3
    print("offline gws: unsupported command", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
