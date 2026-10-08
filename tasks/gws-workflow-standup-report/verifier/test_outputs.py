from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT = RESULTS / "output.json"
MISSING = object()


def pick(mapping: Any, names: tuple[str, ...], default: Any = MISSING) -> Any:
    if isinstance(mapping, dict):
        folded = {str(key).lower().replace("-", "_"): value for key, value in mapping.items()}
        for name in names:
            key = name.lower().replace("-", "_")
            if key in folded:
                return folded[key]
    if default is MISSING:
        raise KeyError(f"none of {names!r} is present")
    return default


def as_rows(value: Any, nested_names: tuple[str, ...] = ("items", "records", "entries")) -> list[dict]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        nested = pick(value, nested_names, default=None)
        if nested is not None:
            return as_rows(nested, nested_names)
        rows = []
        for key, item in value.items():
            if isinstance(item, dict):
                row = dict(item)
                row.setdefault("_map_key", key)
                rows.append(row)
        return rows
    return []


def load_output() -> dict:
    assert OUTPUT.is_file(), "the requested /root/results/output.json was not created"
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AssertionError(f"output.json is not valid UTF-8 JSON: {exc}") from exc
    assert isinstance(payload, dict), "output.json must contain a JSON object"
    for wrapper in ("standup", "standup_report", "report"):
        nested = pick(payload, (wrapper,), default=None)
        if isinstance(nested, dict):
            payload = nested
            break
    return payload


def normalize_output() -> dict:
    payload = load_output()
    rollups = pick(payload, ("rollups", "summaries", "breakdowns"), default={})
    attention = pick(payload, ("attention", "alerts", "risks", "flags"), default={})
    return {
        "raw": payload,
        "report_date": pick(payload, ("report_date", "reportdate", "date", "as_of"), default=None),
        "meetings": as_rows(
            pick(payload, ("meetings", "agenda", "events", "todays_meetings"), default=[]),
            ("items", "records", "entries", "meetings", "events"),
        ),
        "tasks": as_rows(
            pick(payload, ("open_tasks", "tasks", "open_work", "action_items"), default=[]),
            ("items", "records", "entries", "tasks", "open_tasks"),
        ),
        "headline": pick(payload, ("headline", "summary", "counts", "headline_counts"), default={}),
        "attention": attention if isinstance(attention, dict) else {},
        "owner_rollup": pick(
            payload,
            ("owner_rollup", "owner_summary", "by_owner", "owners"),
            default=pick(rollups, ("owner", "owners", "by_owner"), default={}),
        ),
        "priority_rollup": pick(
            payload,
            ("priority_rollup", "priority_summary", "by_priority", "priorities"),
            default=pick(rollups, ("priority", "priorities", "by_priority"), default={}),
        ),
    }


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def source_truth() -> dict:
    meta = json.loads((DATA / "snapshot.json").read_text(encoding="utf-8"))
    events = json.loads((DATA / "calendar_events.json").read_text(encoding="utf-8"))["items"]
    tasks = json.loads((DATA / "tasks.json").read_text(encoding="utf-8"))["items"]
    lists = {
        row["id"]: row["title"]
        for row in json.loads((DATA / "tasklists.json").read_text(encoding="utf-8"))["items"]
    }
    zone = ZoneInfo(meta["timezone"])
    report_day = date.fromisoformat(meta["report_date"])
    day_start = datetime.combine(report_day, time.min, zone)
    day_end = day_start + timedelta(days=1)
    viewer_email = meta["calendar_owner"]["email"]

    def response(event: dict) -> str:
        organizer = event.get("organizer") or {}
        if organizer.get("self") or organizer.get("email") == viewer_email:
            return "accepted"
        for person in event.get("attendees") or []:
            if person.get("self") or person.get("email") == viewer_email:
                return person.get("responseStatus", "needsAction")
        return "needsAction"

    def bounds(event: dict) -> tuple[datetime, datetime, bool]:
        if "date" in event["start"]:
            return (
                datetime.combine(date.fromisoformat(event["start"]["date"]), time.min, zone),
                datetime.combine(date.fromisoformat(event["end"]["date"]), time.min, zone),
                True,
            )
        return (
            parse_dt(event["start"]["dateTime"]).astimezone(zone),
            parse_dt(event["end"]["dateTime"]).astimezone(zone),
            False,
        )

    eligible_events = []
    event_bounds = {}
    for event in events:
        start, end, all_day = bounds(event)
        if event.get("status") == "cancelled" or response(event) == "declined":
            continue
        if end > day_start and start < day_end:
            row = {
                "id": event["id"],
                "title": event["summary"],
                "start": event["start"].get("dateTime", event["start"].get("date")),
                "end": event["end"].get("dateTime", event["end"].get("date")),
                "all_day": all_day,
                "sort_start": start,
            }
            eligible_events.append(row)
            event_bounds[event["id"]] = (start, end, all_day)
    eligible_events.sort(key=lambda row: (not row["all_day"], row["sort_start"], row["id"]))

    conflicts = set()
    for index, left in enumerate(eligible_events):
        left_start, left_end, left_all_day = event_bounds[left["id"]]
        if left_all_day:
            continue
        for right in eligible_events[index + 1 :]:
            right_start, right_end, right_all_day = event_bounds[right["id"]]
            if not right_all_day and max(left_start, right_start) < min(left_end, right_end):
                conflicts.add(frozenset((left["id"], right["id"])))

    open_tasks = []
    for task in tasks:
        if task.get("status") != "needsAction" or task.get("deleted") or task.get("hidden"):
            continue
        due = (task.get("due") or "")[:10] or None
        open_tasks.append(
            {
                "id": task["id"],
                "title": task["title"],
                "owner": task["assignee"]["displayName"],
                "task_list": lists[task["tasklist_id"]],
                "due": due,
                "state": task["workflow_state"],
                "priority": task["priority"],
                "overdue": due is not None and due < meta["report_date"],
            }
        )

    owners = defaultdict(lambda: {"open": 0, "overdue": 0, "blocked": 0})
    priorities = Counter()
    for task in open_tasks:
        owners[task["owner"]]["open"] += 1
        owners[task["owner"]]["overdue"] += int(task["overdue"])
        owners[task["owner"]]["blocked"] += int(task["state"] == "blocked")
        priorities[task["priority"]] += 1

    return {
        "meta": meta,
        "events": eligible_events,
        "conflicts": conflicts,
        "tasks": open_tasks,
        "owners": dict(owners),
        "priorities": dict(priorities),
    }


def text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def date_text(value: Any) -> str | None:
    if value in (None, "", "null"):
        return None
    if isinstance(value, dict):
        value = pick(value, ("date", "datetime", "date_time", "value"), default=None)
    raw = text(value)
    return raw[:10] if raw else None


def bool_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "overdue", "blocked"}:
            return True
        if normalized in {"false", "no", "n", "0", "not overdue", "unblocked"}:
            return False
    return None


def record_identity(row: dict, id_names: tuple[str, ...], title_names: tuple[str, ...]) -> tuple[str, str]:
    identifier = text(pick(row, id_names + ("_map_key",), default=""))
    title = text(pick(row, title_names, default=""))
    return identifier, title


def resolve_records(rows: list[dict], expected: list[dict], *, kind: str) -> tuple[dict[str, dict], list[str]]:
    expected_ids = {row["id"] for row in expected}
    title_to_id = {row["title"].casefold(): row["id"] for row in expected}
    resolved: dict[str, dict] = {}
    order: list[str] = []
    for row in rows:
        if kind == "meeting":
            identifier, title = record_identity(row, ("event_id", "eventid", "id", "meeting_id"), ("title", "summary", "name"))
        else:
            identifier, title = record_identity(row, ("task_id", "taskid", "id", "work_id"), ("title", "summary", "name"))
        canonical = identifier if identifier in expected_ids else title_to_id.get(title.casefold())
        assert canonical is not None, f"unrecognized {kind} record: id={identifier!r}, title={title!r}"
        assert canonical not in resolved, f"duplicate {kind} record for {canonical}"
        resolved[canonical] = row
        order.append(canonical)
    return resolved, order


def same_temporal(actual: Any, expected: str) -> bool:
    if isinstance(actual, dict):
        actual = pick(actual, ("date_time", "datetime", "date", "value"), default="")
    actual_text = text(actual)
    if len(expected) == 10:
        return actual_text[:10] == expected
    try:
        return parse_dt(actual_text).timestamp() == parse_dt(expected).timestamp()
    except (TypeError, ValueError):
        return False


def normalize_pair_token(value: Any, event_title_to_id: dict[str, str]) -> str | None:
    token = text(value)
    if token in event_title_to_id.values():
        return token
    return event_title_to_id.get(token.casefold())


def conflict_pairs(out: dict, meeting_rows: list[dict], expected_events: list[dict]) -> set[frozenset[str]]:
    title_to_id = {row["title"].casefold(): row["id"] for row in expected_events}
    candidates = []
    raw = out["raw"]
    for container in (raw, out["attention"]):
        candidates.extend(
            as_rows(
                pick(container, ("meeting_conflicts", "schedule_conflicts", "conflicts", "overlaps"), default=[]),
                ("items", "records", "entries", "conflicts"),
            )
        )
    for row in meeting_rows:
        left_id, left_title = record_identity(row, ("event_id", "eventid", "id", "meeting_id"), ("title", "summary", "name"))
        left = normalize_pair_token(left_id or left_title, title_to_id)
        linked = pick(row, ("overlaps_with", "conflicts_with", "overlap_ids"), default=[])
        if not isinstance(linked, list):
            linked = [linked]
        for right in linked:
            candidates.append({"event_ids": [left, right]})

    pairs = set()
    for row in candidates:
        values = pick(row, ("event_ids", "meeting_ids", "ids", "pair"), default=None)
        if values is None:
            values = [pick(row, ("left", "first", "event_a"), default=None), pick(row, ("right", "second", "event_b"), default=None)]
        if isinstance(values, str):
            values = [part.strip() for part in values.replace("|", ",").split(",")]
        if not isinstance(values, list) or len(values) != 2:
            continue
        normalized = [normalize_pair_token(value, title_to_id) for value in values]
        if all(normalized) and normalized[0] != normalized[1]:
            pairs.add(frozenset(normalized))
    return pairs


def marked_task_ids(out: dict, rows: list[dict], expected: list[dict], kind: str) -> set[str]:
    expected_map, _ = resolve_records(rows, expected, kind="task")
    title_to_id = {row["title"].casefold(): row["id"] for row in expected}
    aliases = ("overdue_task_ids", "overdue_tasks", "overdue") if kind == "overdue" else ("blocked_task_ids", "blocked_tasks", "blocked")
    explicit = pick(out["attention"], aliases, default=[])
    if isinstance(explicit, dict):
        explicit = list(explicit)
    if not isinstance(explicit, list):
        explicit = [explicit]
    marked = {normalize_pair_token(value, title_to_id) for value in explicit}
    marked.discard(None)
    for canonical, row in expected_map.items():
        if kind == "overdue":
            flag = bool_value(pick(row, ("overdue", "is_overdue", "past_due"), default=None))
            status_text = text(pick(row, ("risk", "flag", "due_status"), default="")).casefold()
            if flag is True or "overdue" in status_text:
                marked.add(canonical)
        else:
            flag = bool_value(pick(row, ("blocked", "is_blocked"), default=None))
            state = text(pick(row, ("workflow_status", "workflow_state", "state", "status"), default="")).casefold()
            reason = text(pick(row, ("blocked_reason", "blocker", "blocking_reason"), default=""))
            if flag is True or state == "blocked" or reason:
                marked.add(canonical)
    return marked


def count_value(mapping: Any, aliases: tuple[str, ...]) -> int | None:
    value = pick(mapping, aliases, default=None)
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_owner_rollup(value: Any) -> dict[str, dict[str, int | None]]:
    result = {}
    if isinstance(value, dict):
        rows = []
        for owner, counts in value.items():
            if isinstance(counts, dict):
                rows.append({"owner": owner, **counts})
    else:
        rows = as_rows(value, ("items", "records", "owners", "by_owner"))
    for row in rows:
        owner = text(pick(row, ("owner", "name", "assignee", "_map_key"), default=""))
        if not owner:
            continue
        result[owner] = {
            "open": count_value(row, ("open", "open_count", "task_count", "tasks")),
            "overdue": count_value(row, ("overdue", "overdue_count", "past_due")),
            "blocked": count_value(row, ("blocked", "blocked_count")),
        }
    return result


def normalize_priority_rollup(value: Any) -> dict[str, int | None]:
    if isinstance(value, dict):
        nested_rows = as_rows(value, ("items", "records", "priorities", "by_priority"))
        if nested_rows:
            value = nested_rows
        else:
            return {text(key).casefold(): int(item) for key, item in value.items() if not isinstance(item, (dict, list, bool))}
    result = {}
    for row in as_rows(value, ("items", "records", "priorities", "by_priority")):
        priority = text(pick(row, ("priority", "name", "level", "_map_key"), default="")).casefold()
        if priority:
            result[priority] = count_value(row, ("open", "count", "open_count", "task_count", "tasks"))
    return result


def test_agenda_accuracy():
    out = normalize_output()
    truth = source_truth()
    actual, order = resolve_records(out["meetings"], truth["events"], kind="meeting")
    expected_ids = {row["id"] for row in truth["events"]}
    assert set(actual) == expected_ids, "the agenda misses an eligible meeting or includes a cancelled, declined, or out-of-day event"
    expected_by_id = {row["id"]: row for row in truth["events"]}
    for event_id, expected in expected_by_id.items():
        row = actual[event_id]
        title = text(pick(row, ("title", "summary", "name"), default=""))
        start = pick(row, ("start", "start_time", "start_at", "begins"), default=None)
        end = pick(row, ("end", "end_time", "end_at", "finishes"), default=None)
        assert title == expected["title"], f"{event_id} has the wrong title"
        assert same_temporal(start, expected["start"]), f"{event_id} has the wrong start"
        assert same_temporal(end, expected["end"]), f"{event_id} has the wrong end"
    actual_timed = [event_id for event_id in order if not expected_by_id[event_id]["all_day"]]
    expected_timed = [row["id"] for row in truth["events"] if not row["all_day"]]
    assert actual_timed == expected_timed, "the timed meetings in the attended agenda are not chronological"
    assert conflict_pairs(out, out["meetings"], truth["events"]) == truth["conflicts"], "meeting conflict flags do not match the timed overlaps"


def test_open_work_accuracy():
    out = normalize_output()
    truth = source_truth()
    actual, _ = resolve_records(out["tasks"], truth["tasks"], kind="task")
    expected_by_id = {row["id"]: row for row in truth["tasks"]}
    assert set(actual) == set(expected_by_id), "the report misses open work or includes completed, deleted, or hidden tasks"
    for task_id, expected in expected_by_id.items():
        row = actual[task_id]
        title = text(pick(row, ("title", "summary", "name"), default=""))
        owner_value = pick(row, ("owner", "assignee", "assigned_to"), default="")
        if isinstance(owner_value, dict):
            owner_value = pick(owner_value, ("display_name", "displayname", "name", "email"), default="")
        due = date_text(pick(row, ("due_date", "due", "deadline"), default=None))
        priority = text(pick(row, ("priority", "priority_level", "urgency"), default="")).casefold()
        assert title == expected["title"], f"{task_id} has the wrong title"
        assert text(owner_value) == expected["owner"], f"{task_id} has the wrong owner"
        assert due == expected["due"], f"{task_id} has the wrong due date"
        assert priority == expected["priority"], f"{task_id} has the wrong priority"
    expected_overdue = {row["id"] for row in truth["tasks"] if row["overdue"]}
    expected_blocked = {row["id"] for row in truth["tasks"] if row["state"] == "blocked"}
    assert marked_task_ids(out, out["tasks"], truth["tasks"], "overdue") == expected_overdue, "overdue work is not flagged exactly"
    assert marked_task_ids(out, out["tasks"], truth["tasks"], "blocked") == expected_blocked, "blocked work is not flagged exactly"


def test_rollup_consistency():
    out = normalize_output()
    truth = source_truth()
    headline = out["headline"]
    expected_headline = {
        "meeting": len(truth["events"]),
        "open": len(truth["tasks"]),
        "overdue": sum(row["overdue"] for row in truth["tasks"]),
        "blocked": sum(row["state"] == "blocked" for row in truth["tasks"]),
        "conflict": len(truth["conflicts"]),
    }
    actual_headline = {
        "meeting": count_value(headline, ("meeting_count", "meetings_count", "meetings", "agenda_count")),
        "open": count_value(headline, ("open_task_count", "open_tasks_count", "task_count", "open_work_count", "tasks")),
        "overdue": count_value(headline, ("overdue_task_count", "overdue_count", "past_due_count", "overdue")),
        "blocked": count_value(headline, ("blocked_task_count", "blocked_count", "blocked")),
        "conflict": count_value(headline, ("meeting_conflict_count", "conflict_count", "schedule_conflict_count", "conflicts")),
    }
    assert actual_headline == expected_headline, "headline counts do not reconcile with the source snapshot"
    actual_owners = normalize_owner_rollup(out["owner_rollup"])
    assert set(actual_owners) == set(truth["owners"]), "the owner rollup misses or invents an owner"
    for owner, expected in truth["owners"].items():
        assert actual_owners[owner]["open"] == expected["open"], f"{owner} has the wrong open-task total"
        for optional_dimension in ("overdue", "blocked"):
            value = actual_owners[owner][optional_dimension]
            if value is not None:
                assert value == expected[optional_dimension], f"{owner} has the wrong {optional_dimension} total"
    assert normalize_priority_rollup(out["priority_rollup"]) == truth["priorities"], "priority totals are inconsistent"
