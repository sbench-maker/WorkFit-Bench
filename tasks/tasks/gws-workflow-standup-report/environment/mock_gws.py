#!/usr/bin/env python3
"""Offline, read-only stand-in for `gws workflow +standup-report`."""

from __future__ import annotations

import csv
import io
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def self_response(event: dict, viewer_email: str) -> str:
    organizer = event.get("organizer") or {}
    if organizer.get("self") or organizer.get("email") == viewer_email:
        return "accepted"
    for person in event.get("attendees") or []:
        if person.get("self") or person.get("email") == viewer_email:
            return person.get("responseStatus", "needsAction")
    return "needsAction"


def event_bounds(event: dict, zone: ZoneInfo) -> tuple[datetime, datetime, bool]:
    start, end = event["start"], event["end"]
    if "date" in start:
        return (
            datetime.combine(date.fromisoformat(start["date"]), time.min, zone),
            datetime.combine(date.fromisoformat(end["date"]), time.min, zone),
            True,
        )
    return (
        parse_datetime(start["dateTime"]).astimezone(zone),
        parse_datetime(end["dateTime"]).astimezone(zone),
        False,
    )


def build_report() -> dict:
    meta = load("snapshot.json")
    zone = ZoneInfo(meta["timezone"])
    report_date = date.fromisoformat(meta["report_date"])
    day_start = datetime.combine(report_date, time.min, zone)
    day_end = day_start + timedelta(days=1)

    meetings = []
    for event in load("calendar_events.json")["items"]:
        start, end, all_day = event_bounds(event, zone)
        response = self_response(event, meta["calendar_owner"]["email"])
        if event.get("status") == "cancelled" or response == "declined":
            continue
        if not (end > day_start and start < day_end):
            continue
        meetings.append(
            {
                "event_id": event["id"],
                "title": event["summary"],
                "start": event["start"].get("dateTime", event["start"].get("date")),
                "end": event["end"].get("dateTime", event["end"].get("date")),
                "all_day": all_day,
                "location": event.get("location", ""),
                "response_status": response,
            }
        )
    meetings.sort(key=lambda row: (not row["all_day"], event_bounds({"start": {"date": row["start"]}, "end": {"date": row["end"]}}, zone)[0] if row["all_day"] else parse_datetime(row["start"]).astimezone(zone), row["event_id"]))

    bounds = {}
    for event in load("calendar_events.json")["items"]:
        if event["id"] in {row["event_id"] for row in meetings}:
            bounds[event["id"]] = event_bounds(event, zone)
    conflicts = []
    for index, left in enumerate(meetings):
        left_start, left_end, left_all_day = bounds[left["event_id"]]
        if left_all_day:
            continue
        for right in meetings[index + 1 :]:
            right_start, right_end, right_all_day = bounds[right["event_id"]]
            if not right_all_day and max(left_start, right_start) < min(left_end, right_end):
                conflicts.append({"event_ids": [left["event_id"], right["event_id"]], "reason": "time overlap"})

    list_names = {row["id"]: row["title"] for row in load("tasklists.json")["items"]}
    priority_rank = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    tasks = []
    for task in load("tasks.json")["items"]:
        if task.get("status") != "needsAction" or task.get("deleted") or task.get("hidden"):
            continue
        due_value = task.get("due") or ""
        due_date = due_value[:10] or None
        overdue = due_date is not None and due_date < meta["report_date"]
        blocked = task.get("workflow_state") == "blocked"
        tasks.append(
            {
                "task_id": task["id"],
                "title": task["title"],
                "owner": task["assignee"]["displayName"],
                "task_list": list_names[task["tasklist_id"]],
                "project": task["project"],
                "due_date": due_date,
                "workflow_status": task["workflow_state"],
                "priority": task["priority"],
                "overdue": overdue,
                "blocked_reason": task["notes"].removeprefix("BLOCKED: ") if blocked else None,
            }
        )
    tasks.sort(
        key=lambda row: (
            row["workflow_status"] != "blocked",
            not row["overdue"],
            priority_rank.get(row["priority"], 9),
            row["due_date"] is None,
            row["due_date"] or "9999-12-31",
            row["task_id"],
        )
    )

    owner_rollup = defaultdict(lambda: {"open": 0, "overdue": 0, "blocked": 0})
    priority_rollup = Counter()
    for task in tasks:
        row = owner_rollup[task["owner"]]
        row["open"] += 1
        row["overdue"] += int(task["overdue"])
        row["blocked"] += int(task["workflow_status"] == "blocked")
        priority_rollup[task["priority"]] += 1

    return {
        "report_date": meta["report_date"],
        "timezone": meta["timezone"],
        "headline": {
            "meeting_count": len(meetings),
            "open_task_count": len(tasks),
            "overdue_task_count": sum(row["overdue"] for row in tasks),
            "blocked_task_count": sum(row["workflow_status"] == "blocked" for row in tasks),
            "meeting_conflict_count": len(conflicts),
        },
        "attention": {
            "meeting_conflicts": conflicts,
            "overdue_task_ids": [row["task_id"] for row in tasks if row["overdue"]],
            "blocked_task_ids": [row["task_id"] for row in tasks if row["workflow_status"] == "blocked"],
        },
        "meetings": meetings,
        "open_tasks": tasks,
        "owner_rollup": [
            {"owner": owner, **counts} for owner, counts in sorted(owner_rollup.items())
        ],
        "priority_rollup": [
            {"priority": priority, "open": priority_rollup.get(priority, 0)}
            for priority in ("urgent", "high", "medium", "low")
        ],
    }


def emit_table(report: dict) -> str:
    lines = [
        f"Standup report {report['report_date']} ({report['timezone']})",
        json.dumps(report["headline"], sort_keys=True),
        "MEETINGS",
    ]
    lines.extend(f"{row['start']}\t{row['title']}" for row in report["meetings"])
    lines.append("OPEN TASKS")
    lines.extend(f"{row['priority']}\t{row['owner']}\t{row['title']}" for row in report["open_tasks"])
    return "\n".join(lines)


def emit_csv(report: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["kind", "id", "title", "owner_or_start", "due_or_end", "priority"])
    for row in report["meetings"]:
        writer.writerow(["meeting", row["event_id"], row["title"], row["start"], row["end"], ""])
    for row in report["open_tasks"]:
        writer.writerow(["task", row["task_id"], row["title"], row["owner"], row["due_date"] or "", row["priority"]])
    return buffer.getvalue().rstrip()


def emit_yaml(report: dict) -> str:
    # JSON is valid YAML 1.2 and keeps the mock dependency-free.
    return json.dumps(report, ensure_ascii=False, indent=2)


def main() -> int:
    args = sys.argv[1:]
    if not args or args in (["--help"], ["help"]):
        print("offline gws: workflow +standup-report [--format json|table|yaml|csv]")
        return 0
    if args == ["--version"]:
        print("gws offline-mock 0.22.5")
        return 0
    if args[:2] != ["workflow", "+standup-report"]:
        print("offline gws: only workflow +standup-report is available", file=sys.stderr)
        return 2
    if "--help" in args:
        print("Today's meetings + open tasks as a standup summary. Formats: json, table, yaml, csv.")
        return 0
    output_format = "json"
    if "--format" in args:
        try:
            output_format = args[args.index("--format") + 1]
        except IndexError:
            print("--format requires a value", file=sys.stderr)
            return 2
    report = build_report()
    if output_format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif output_format == "table":
        print(emit_table(report))
    elif output_format == "csv":
        print(emit_csv(report))
    elif output_format == "yaml":
        print(emit_yaml(report))
    else:
        print(f"unsupported format: {output_format}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
