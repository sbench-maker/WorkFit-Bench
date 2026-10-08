from __future__ import annotations

import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import pytest


DATA = Path(os.environ.get("PROJECT_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("PROJECT_OUTPUT_PATH", "/root/results/output.json"))


def _csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _status(value: Any) -> str:
    aliases = {
        "backlog": "Backlog", "ready": "Ready", "inprogress": "In Progress",
        "inreview": "In Review", "review": "In Review", "blocked": "Blocked",
        "done": "Done", "complete": "Done", "completed": "Done",
        "cancelled": "Cancelled", "canceled": "Cancelled",
    }
    return aliases.get(_key(value), str(value).strip())


def _blocker_matches(actual: Any, expected: str) -> bool:
    actual_key = _key(actual or "")
    if not expected:
        return not actual_key or actual_key in {"none", "null", "notblocked", "cleared"}
    required_terms = {
        "Waiting for vendor tax-code sample": ("vendor", "tax", "sample"),
        "Security approval needed for token migration": ("security", "approval", "token", "migration"),
    }.get(expected)
    if required_terms:
        return all(term in actual_key for term in required_terms)
    return actual_key == _key(expected)


def _get(row: dict, *aliases: str, default: Any = None) -> Any:
    keyed = {_key(key): value for key, value in row.items()}
    for alias in aliases:
        if _key(alias) in keyed:
            return keyed[_key(alias)]
    return default


def _walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _load() -> tuple[Any | None, str | None]:
    if not OUTPUT.is_file():
        return None, f"requested artifact is missing: {OUTPUT}"
    try:
        value = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"output.json is not readable JSON: {exc}"
    if not isinstance(value, (dict, list)):
        return None, "output.json must contain a JSON object or list"
    return value, None


def _usable() -> Any:
    payload, error = _load()
    if error:
        pytest.skip(f"semantic checks skipped because artifact usability already captures the root problem: {error}")
    return payload


def _collection(payload: Any, aliases: tuple[str, ...], predicate) -> list[dict]:
    wanted = {_key(alias) for alias in aliases}
    for node in _walk(payload):
        if isinstance(node, dict):
            for key, value in node.items():
                if _key(key) in wanted and isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
    # Representation-neutral fallback for plans with one mixed `actions` list.
    records: list[dict] = []
    seen: set[int] = set()
    for node in _walk(payload):
        if isinstance(node, dict) and predicate(node) and id(node) not in seen:
            records.append(node)
            seen.add(id(node))
    return records


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[|,;]", value) if item.strip()]
    return [value]


PEOPLE = {row["member_id"]: row for row in _csv("team_members.csv")}
PERSON_ALIASES: dict[str, str] = {}
for person_id, row in PEOPLE.items():
    for value in (person_id, row["name"], row["email"]):
        PERSON_ALIASES[_key(value)] = person_id


def _person_ids(value: Any) -> set[str]:
    found: set[str] = set()
    for item in _as_list(value):
        if isinstance(item, dict):
            item = _get(item, "member_id", "stakeholder_id", "id", "email", "name")
        alias = PERSON_ALIASES.get(_key(item))
        if alias:
            found.add(alias)
    return found


def _source_truth() -> dict[str, Any]:
    workspace = json.loads((DATA / "workspace.json").read_text(encoding="utf-8"))
    project_id = workspace["target_project_id"]
    tasks = {row["task_id"]: row for row in _csv("project_tasks.csv") if row["project_id"] == project_id}
    eligible: dict[str, list[dict[str, str]]] = defaultdict(list)
    for event in _csv("task_status_events.csv"):
        task = tasks.get(event["task_id"])
        if task is None or event["project_id"] != project_id:
            continue
        role = PEOPLE.get(event["reporter_id"], {}).get("role")
        authorized = event["reporter_id"] == task["owner_id"] or role == "project_manager"
        if not authorized or event["duplicate_of"] or _dt(event["received_at"]) <= _dt(task["tracker_updated_at"]):
            continue
        if task["status"] == "Done" and event["reported_status"] != "Done" and event["reopen"].lower() != "true":
            continue
        eligible[event["task_id"]].append(event)
    effective = {task_id: dict(row) for task_id, row in tasks.items()}
    updates: dict[str, dict] = {}
    for task_id, events in eligible.items():
        event = max(events, key=lambda row: _dt(row["received_at"]))
        task = tasks[task_id]
        changed = any((
            event["reported_status"] != task["status"],
            event["percent_complete"] != task["percent_complete"],
            event["blocker_reason"] != task["blocker_reason"],
        ))
        if changed:
            updates[task_id] = {
                "from": task["status"], "to": event["reported_status"], "percent": int(event["percent_complete"]),
                "blocker": event["blocker_reason"], "event": event["event_id"],
            }
            effective[task_id].update(status=event["reported_status"], percent_complete=event["percent_complete"], blocker_reason=event["blocker_reason"])
    report_day = date.fromisoformat(workspace["reporting_date"])
    counts = dict(Counter(row["status"] for row in effective.values()))
    overdue = {
        task_id for task_id, row in effective.items()
        if date.fromisoformat(row["due_date"]) < report_day and row["status"] not in {"Done", "Cancelled"}
    }
    blockers = {task_id for task_id, row in effective.items() if row["status"] == "Blocked"}
    return {"workspace": workspace, "tasks": tasks, "effective": effective, "updates": updates, "counts": counts, "overdue": overdue, "blockers": blockers}


TRUTH = _source_truth()


def _tracker_records(payload: Any) -> list[dict]:
    return _collection(
        payload,
        ("tracker_updates", "task_updates", "sheet_updates", "tracker_mutations"),
        lambda row: _get(row, "task_id", "ticket_id") is not None and _get(row, "to_status", "new_status", "status") is not None,
    )


def _snapshot(payload: Any) -> dict | None:
    aliases = {_key(name) for name in ("weekly_snapshot", "weekly_digest", "project_summary", "digest", "summary")}
    for node in _walk(payload):
        if isinstance(node, dict):
            for key, value in node.items():
                if _key(key) in aliases and isinstance(value, dict):
                    return value
    for node in _walk(payload):
        if isinstance(node, dict) and _get(node, "status_counts", "counts_by_status") is not None:
            return node
    return None


def _status_counts(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        result: dict[str, int] = defaultdict(int)
        for key, number in value.items():
            result[_status(key)] += int(number)
        return dict(result)
    result = {}
    for item in _as_list(value):
        if isinstance(item, dict):
            label = _get(item, "status", "name", "label")
            number = _get(item, "count", "total", "value")
            if label is not None and number is not None:
                result[_status(label)] = int(number)
    return result


def _id_set(value: Any, aliases: tuple[str, ...]) -> set[str]:
    result = set()
    for item in _as_list(value):
        if isinstance(item, dict):
            item = _get(item, *aliases)
        if item is not None:
            result.add(str(item))
    return result


def _expected_meetings() -> dict[str, dict]:
    workspace = TRUTH["workspace"]
    availability = defaultdict(list)
    for row in _csv("availability.csv"):
        availability[(row["member_id"], row["date"])].append((row["available_from"], row["available_to"]))
    calendar = _csv("calendar_events.csv")
    existing = {row["linked_request_id"] for row in calendar if row["linked_request_id"]}
    busy = defaultdict(list)
    for row in calendar:
        for attendee in row["attendee_ids"].split("|"):
            if attendee:
                busy[(attendee, row["start"][:10])].append((_dt(row["start"]), _dt(row["end"])))

    def free(member: str, day: str, start: datetime, end: datetime) -> bool:
        hm_start, hm_end = start.strftime("%H:%M"), end.strftime("%H:%M")
        allowed = any(lo <= hm_start and hm_end <= hi for lo, hi in availability[(member, day)])
        no_overlap = all(not (start < old_end and end > old_start) for old_start, old_end in busy[(member, day)])
        return allowed and no_overlap

    expected = {}
    requests = json.loads((DATA / "meeting_requests.json").read_text(encoding="utf-8"))
    for request in requests:
        if request["request_id"] in existing:
            continue
        duration = timedelta(minutes=request["duration_minutes"])
        first_day = request["recurrence_dates"][0]
        cursor = _dt(f"{first_day}T{request['window_start']}:00-04:00")
        limit = _dt(f"{first_day}T{request['window_end']}:00-04:00")
        while cursor + duration <= limit:
            hm = cursor.strftime("%H:%M")
            if all(
                all(free(member, day, _dt(f"{day}T{hm}:00-04:00"), _dt(f"{day}T{hm}:00-04:00") + duration) for member in request["required_attendee_ids"])
                for day in request["recurrence_dates"]
            ):
                break
            cursor += timedelta(minutes=workspace["scheduling_rules"]["slot_increment_minutes"])
        attendees = set(request["required_attendee_ids"])
        if request["include_optional_if_available"] and not request["sensitive"]:
            for member in request["optional_attendee_ids"]:
                if all(free(member, day, _dt(f"{day}T{cursor.strftime('%H:%M')}:00-04:00"), _dt(f"{day}T{cursor.strftime('%H:%M')}:00-04:00") + duration) for day in request["recurrence_dates"]):
                    attendees.add(member)
        expected[request["request_id"]] = {
            "occurrences": {(day, cursor.strftime("%H:%M"), (_dt(f"{day}T{cursor.strftime('%H:%M')}:00-04:00") + duration).strftime("%H:%M")) for day in request["recurrence_dates"]},
            "attendees": attendees, "duration": request["duration_minutes"],
        }
    return expected


EXPECTED_MEETINGS = _expected_meetings()


def _meeting_records(payload: Any) -> list[dict]:
    return _collection(
        payload,
        ("calendar_creations", "calendar_events", "meeting_actions", "meetings", "calendar_creates"),
        lambda row: _get(row, "request_id", "meeting_request_id", "linked_request_id") is not None,
    )


def _occurrences(row: dict) -> set[tuple[str, str, str]]:
    raw = _get(row, "occurrences", "instances", "dates")
    items = raw if isinstance(raw, list) else [row]
    result: set[tuple[str, str, str]] = set()
    duration = _get(row, "duration_minutes", "duration", default=0)
    for item in items:
        if isinstance(item, str):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", item):
                start_value = _get(row, "start_time", "time", "start")
                end_value = _get(row, "end_time", "end")
                if start_value and "T" not in str(start_value):
                    start_value = f"{item}T{start_value}:00-04:00"
                if end_value and "T" not in str(end_value):
                    end_value = f"{item}T{end_value}:00-04:00"
            else:
                start_value, end_value = item, None
        elif isinstance(item, dict):
            start_value = _get(item, "start", "start_at", "start_time", "datetime")
            end_value = _get(item, "end", "end_at", "end_time")
            day_value = _get(item, "date", "day")
            if day_value and start_value and "T" not in str(start_value):
                start_value = f"{day_value}T{start_value}:00-04:00"
            if day_value and end_value and "T" not in str(end_value):
                end_value = f"{day_value}T{end_value}:00-04:00"
        else:
            continue
        if not start_value:
            continue
        try:
            start = _dt(str(start_value))
            end = _dt(str(end_value)) if end_value else start + timedelta(minutes=int(duration))
        except (ValueError, TypeError):
            continue
        result.add((start.date().isoformat(), start.strftime("%H:%M"), end.strftime("%H:%M")))
    return result


def _email_records(payload: Any) -> list[dict]:
    return _collection(
        payload,
        ("email_drafts", "emails", "status_emails", "outbound_emails"),
        lambda row: _get(row, "subject") is not None and _get(row, "body", "message", "content") is not None,
    )


def _document_records(payload: Any) -> list[dict]:
    return _collection(
        payload,
        ("document_actions", "file_announcements", "announcements", "shared_documents"),
        lambda row: _get(row, "document_id", "file_id", "doc_id") is not None and _get(row, "channel", "announce_to") is not None,
    )


def test_tracker_reconciliation_and_weekly_snapshot() -> None:
    payload = _usable()
    records = _tracker_records(payload)
    actual: dict[str, dict] = {}
    duplicates = []
    for row in records:
        task_id = str(_get(row, "task_id", "ticket_id", "work_item_id", default=""))
        if task_id in actual:
            duplicates.append(task_id)
        actual[task_id] = row
    expected = TRUTH["updates"]
    assert set(actual) == set(expected), (
        f"tracker mutation scope differs: missing={sorted(set(expected)-set(actual))}, extra={sorted(set(actual)-set(expected))}; "
        "the dry-run would omit valid updates or write unsupported changes"
    )
    assert not duplicates, f"tracker mutations are duplicated for {duplicates}"
    errors = []
    for task_id, truth in expected.items():
        row = actual[task_id]
        to_status = _status(_get(row, "to_status", "new_status", "status", "reported_status", default=""))
        pct = _get(row, "percent_complete", "completion_percent", "progress")
        blocker = _get(row, "blocker_reason", "blocker", "blocking_reason", default="") or ""
        event_id = str(_get(row, "effective_event_id", "source_event_id", "update_id", "event_id", default=""))
        if to_status != truth["to"] or int(pct) != truth["percent"] or not _blocker_matches(blocker, truth["blocker"]) or event_id != truth["event"]:
            errors.append(f"{task_id}: got status={to_status!r}, percent={pct!r}, blocker={blocker!r}, event={event_id!r}; expected {truth}")
    assert not errors, "incorrect effective tracker changes:\n" + "\n".join(errors)

    snapshot = _snapshot(payload)
    assert snapshot is not None, "the weekly post-reconciliation snapshot is missing"
    counts = _status_counts(_get(snapshot, "status_counts", "counts_by_status", "task_counts"))
    assert counts == TRUTH["counts"], f"post-reconciliation status counts are {counts}, expected {TRUTH['counts']}"
    overdue = _id_set(_get(snapshot, "overdue_open_task_ids", "overdue_tasks", "overdue_open"), ("task_id", "ticket_id", "id"))
    blockers = _id_set(_get(snapshot, "active_blockers", "blocked_tasks", "blockers"), ("task_id", "ticket_id", "id"))
    assert overdue == TRUTH["overdue"], f"overdue open work is {sorted(overdue)}, expected {sorted(TRUTH['overdue'])}"
    assert blockers == TRUTH["blockers"], f"active blocker scope is wrong: missing={sorted(TRUTH['blockers']-blockers)}, extra={sorted(blockers-TRUTH['blockers'])}"


def test_calendar_actions_are_feasible_complete_and_deduplicated() -> None:
    payload = _usable()
    records = _meeting_records(payload)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        request_id = str(_get(row, "request_id", "meeting_request_id", "linked_request_id", default=""))
        grouped[request_id].append(row)
    assert set(grouped) == set(EXPECTED_MEETINGS), (
        f"calendar creation scope differs: missing={sorted(set(EXPECTED_MEETINGS)-set(grouped))}, "
        f"extra={sorted(set(grouped)-set(EXPECTED_MEETINGS))}; MEET-104 must not be recreated"
    )
    errors = []
    for request_id, expected in EXPECTED_MEETINGS.items():
        actual_occurrences: set[tuple[str, str, str]] = set()
        attendee_sets: list[set[str]] = []
        for row in grouped[request_id]:
            actual_occurrences |= _occurrences(row)
            attendees = _person_ids(_get(row, "attendee_ids", "attendees", "participants", "invitees"))
            if attendees:
                attendee_sets.append(attendees)
        if actual_occurrences != expected["occurrences"]:
            errors.append(f"{request_id} occurrences {sorted(actual_occurrences)} != {sorted(expected['occurrences'])}")
        if not attendee_sets or any(attendees != expected["attendees"] for attendees in attendee_sets):
            errors.append(f"{request_id} attendees {attendee_sets} != {expected['attendees']}")
    assert not errors, "calendar actions violate timing, attendance, recurrence, or sensitivity rules:\n" + "\n".join(errors)


def test_email_draft_scope_routing_and_deduplication() -> None:
    payload = _usable()
    records = _email_records(payload)
    weekly = []
    blockers: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        kind = _key(_get(row, "kind", "type", "email_type", default=""))
        task_id = str(_get(row, "related_task_id", "task_id", "ticket_id", default=""))
        period = str(_get(row, "reporting_period", "week_of", "report_date", default=""))
        if "weekly" in kind or (period == "2026-10-05" and not task_id):
            weekly.append(row)
        elif task_id:
            blockers[task_id].append(row)
    assert len(weekly) == 1, f"expected one current weekly status draft, found {len(weekly)}"
    assert set(blockers) == {"ORBIT-012"} and len(blockers["ORBIT-012"]) == 1, (
        f"blocker draft scope is {sorted(blockers)}; only ORBIT-012 needs a new escalation after cooldown deduplication"
    )
    weekly_recipients = _person_ids(_get(weekly[0], "recipient_ids", "recipients", "to", "to_addresses"))
    blocker_row = blockers["ORBIT-012"][0]
    blocker_recipients = _person_ids(_get(blocker_row, "recipient_ids", "recipients", "to", "to_addresses"))
    assert weekly_recipients == {"AVA", "COLE", "OWEN"}, f"weekly stakeholder recipients are {weekly_recipients}"
    assert blocker_recipients == {"MAYA", "NINA"}, f"ORBIT-012 escalation recipients are {blocker_recipients}"
    for label, row in (("weekly status", weekly[0]), ("ORBIT-012 escalation", blocker_row)):
        subject = str(_get(row, "subject", default="")).strip()
        body = str(_get(row, "body", "message", "content", default="")).strip()
        assert subject and body, f"{label} needs a reviewable subject and body"
    combined = json.dumps(blocker_row, ensure_ascii=False)
    assert "ORBIT-012" in combined, "the blocker escalation is not tied clearly to ORBIT-012"


def test_document_upload_and_announcement_scope() -> None:
    payload = _usable()
    records = _document_records(payload)
    document_ids = [str(_get(row, "document_id", "file_id", "doc_id", default="")) for row in records]
    assert document_ids and set(document_ids) == {"DOC-RUNBOOK-V3"}, (
        f"document action scope is {document_ids}; only the newest approved team-visible unannounced version is eligible"
    )
    channels = {str(_get(row, "channel", "announce_to", "destination", default="")).lstrip("#").lower() for row in records if _get(row, "channel", "announce_to", "destination")}
    versions = {int(_get(row, "version", "document_version")) for row in records if _get(row, "version", "document_version") is not None}
    sources = {str(_get(row, "source_path", "local_path", "path")) for row in records if _get(row, "source_path", "local_path", "path")}
    messages = [str(_get(row, "announcement", "message", "body", "text", default="")).strip() for row in records]
    actions = " ".join(_key(_get(row, "action", "operation", "type", default="")) for row in records)
    flags = any(_get(row, "upload") and _get(row, "announce") for row in records)
    assert channels == {"orbit-launch"}, f"the approved runbook announcement targets {channels!r}, not orbit-launch"
    assert not versions or versions == {3}, f"the action identifies runbook version(s) {versions!r}, not v3"
    assert all(source.endswith("/artifacts/orbit_launch_runbook_v3.md") for source in sources), f"an upload source points to the wrong version: {sources}"
    assert ("upload" in actions and "announce" in actions) or flags, "the plan must cover both upload and channel announcement"
    assert any(messages), "the document action lacks the announcement draft needed for review"
