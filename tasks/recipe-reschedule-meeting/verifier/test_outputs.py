from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT_PATH = RESULTS_DIR / "output.json"
FIXTURE_ZONES = {
    "America/New_York": timezone(timedelta(hours=-4)),
    "America/Los_Angeles": timezone(timedelta(hours=-7)),
}


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


ALIASES = {
    "id": {"id", "eventid", "eventidentifier", "uid"},
    "start": {"start", "newstart", "starttime", "begin", "begins", "from"},
    "end": {"end", "newend", "endtime", "finish", "ends", "to"},
    "datetime": {"datetime", "dateandtime", "timestamp", "value"},
    "timezone": {"timezone", "tz", "ianatimezone"},
    "attendees": {"attendees", "guests", "invitees", "participants"},
    "email": {"email", "address", "recipient", "recipientemail"},
    "send_updates": {"sendupdates", "notify", "notificationmode", "updatemode"},
    "before": {"before", "original", "previousevent", "originalevent", "priorstate"},
    "after": {"after", "updated", "updatedevent", "event", "result", "newstate", "calendarevent"},
    "notifications": {
        "notifications",
        "notifiedattendees",
        "attendeesnotified",
        "notificationrecipients",
        "recipients",
        "deliveries",
    },
    "status": {"status", "resultstatus", "outcome"},
    "scope": {"scope", "updatescope", "recurrencescope"},
}


def walk(value: object):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def field(record: dict, alias: str) -> Any:
    names = ALIASES[alias]
    for key, value in record.items():
        if norm(key) in names:
            return value
    return None


def first_value(doc: object, alias: str) -> Any:
    for node in walk(doc):
        if isinstance(node, dict):
            value = field(node, alias)
            if value is not None:
                return value
    return None


def load_output() -> object:
    assert OUTPUT_PATH.is_file(), "output.json is missing, so the completed calendar change cannot be reviewed"
    try:
        value = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        pytest.fail(f"output.json is not readable JSON: {exc}")
    assert isinstance(value, (dict, list)), "output.json must contain a JSON object or list"
    return value


def source() -> tuple[dict, list[dict], dict]:
    request = json.loads((DATA_DIR / "reschedule_request.json").read_text(encoding="utf-8"))
    events = json.loads((DATA_DIR / "calendar_events.json").read_text(encoding="utf-8"))["events"]
    clues = request["target_clues"]
    matches = [
        item
        for item in events
        if item["calendarId"] == clues["calendar_id"]
        and item["summary"] == clues["summary"]
        and item["status"] != "cancelled"
        and item["start"]["dateTime"] == clues["current_start_local"]
        and item["organizer"]["email"] == clues["organizer_email"]
    ]
    assert len(matches) == 1, "the frozen request does not resolve to exactly one source event"
    return request, events, matches[0]


def record_id(record: dict) -> str:
    value = field(record, "id")
    return str(value).strip() if value is not None else ""


def event_records(value: object) -> list[dict]:
    records: list[dict] = []
    seen: set[int] = set()
    for node in walk(value):
        if not isinstance(node, dict) or id(node) in seen:
            continue
        if record_id(node) and field(node, "start") is not None and field(node, "end") is not None:
            records.append(node)
            seen.add(id(node))
    return records


def section_values(doc: object, alias: str) -> list[object]:
    values: list[object] = []
    for node in walk(doc):
        if not isinstance(node, dict):
            continue
        names = ALIASES[alias]
        for key, value in node.items():
            if norm(key) in names:
                values.append(value)
    return values


def find_state_event(doc: object, alias: str, target_id: str) -> dict | None:
    candidates: list[dict] = []
    seen: set[int] = set()
    for value in section_values(doc, alias):
        if (
            isinstance(value, dict)
            and id(value) not in seen
            and record_id(value)
            and field(value, "start") is not None
        ):
            candidates.append(value)
            seen.add(id(value))
        for record in event_records(value):
            if id(record) not in seen:
                candidates.append(record)
                seen.add(id(record))
    matches = [record for record in candidates if record_id(record) == target_id]
    if matches:
        return matches[0]
    if alias == "after":
        # The offline calendar tool persists the complete post-update state in
        # calendar_state.json while output.json is a concise operation receipt.
        state_path = OUTPUT_PATH.parent / "calendar_state.json"
        try:
            state_doc = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state_doc = None
        state_matches = [record for record in event_records(state_doc) if record_id(record) == target_id]
        if len(state_matches) == 1:
            return state_matches[0]
    if len(candidates) == 1:
        return candidates[0]
    # A concise receipt may identify the event once at the document root and
    # keep only changed fields inside `original` / `updated`.
    root_id = first_value(doc, "id")
    state_values = [
        value
        for value in section_values(doc, alias)
        if isinstance(value, dict)
        and field(value, "start") is not None
        and field(value, "end") is not None
    ]
    if str(root_id or "").strip() == target_id and len(state_values) == 1:
        return {"id": target_id, **state_values[0]}
    return None


def extract_datetime(value: object) -> datetime | None:
    if isinstance(value, dict):
        nested = field(value, "datetime")
        if nested is None:
            for key, candidate in value.items():
                if norm(key) in {"date", "iso", "isodatetime"}:
                    nested = candidate
                    break
        parsed = extract_datetime(nested)
        if parsed is not None:
            return parsed
        if isinstance(nested, str):
            try:
                naive = datetime.fromisoformat(nested.strip())
                zone_name = timezone_name(value)
                if naive.tzinfo is None and zone_name in FIXTURE_ZONES:
                    return naive.replace(tzinfo=FIXTURE_ZONES[zone_name])
            except (ValueError, KeyError):
                return None
        return None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def interval(record: dict | None) -> tuple[datetime, datetime] | None:
    if not isinstance(record, dict):
        return None
    start = extract_datetime(field(record, "start"))
    end = extract_datetime(field(record, "end"))
    if start is None or end is None:
        return None
    return start, end


def timezone_name(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    timezone = field(value, "timezone")
    return str(timezone).strip() if timezone is not None else ""


def emails(value: object) -> set[str]:
    found: set[str] = set()
    for node in walk(value):
        if isinstance(node, str) and "@" in node:
            found.add(node.strip().lower())
        elif isinstance(node, dict):
            email = field(node, "email")
            if isinstance(email, str) and "@" in email:
                found.add(email.strip().lower())
    return found


def comparable(value: object) -> object:
    if isinstance(value, dict):
        return {norm(key): comparable(item) for key, item in value.items() if norm(key) != "updated"}
    if isinstance(value, list):
        normalized = [comparable(item) for item in value]
        return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True))
    return value


def test_artifact_usability():
    """Criterion: artifact_usability."""
    doc = load_output()
    request, _, target = source()
    after = find_state_event(doc, "after", target["id"])
    explicit_id = first_value(doc, "id")
    assert after is not None, "the receipt does not expose an identifiable updated event with start and end times"
    assert explicit_id is not None, "the receipt does not identify which calendar event was updated"
    status = first_value(doc, "status")
    if status is not None:
        assert norm(status) in {"updated", "success", "succeeded", "completed", "applied", "queued"}, (
            "the receipt status does not show a completed or accepted calendar update"
        )
    assert request["request_id"], "the bundled request is invalid"


def test_correct_event_and_occurrence_scope():
    """Criterion: event_selection."""
    doc = load_output()
    _, events, target = source()
    ids = {
        record_id(record)
        for record in event_records(doc)
        if record_id(record)
    }
    for node in walk(doc):
        if isinstance(node, dict):
            for key, value in node.items():
                if norm(key) in ALIASES["id"] and isinstance(value, str):
                    ids.add(value.strip())
    assert target["id"] in ids, "the update receipt does not identify the intended Aurora occurrence"
    after = find_state_event(doc, "after", target["id"])
    assert after is not None and record_id(after) == target["id"], (
        "the updated event is a similarly named decoy or a series-level record rather than the requested occurrence"
    )
    forbidden = {
        item["id"]
        for item in events
        if item["id"] != target["id"]
        and (item["summary"].startswith("Aurora Color Review") or item.get("recurringEventId") == target["recurringEventId"])
    }
    changed_ids = {
        record_id(record)
        for value in section_values(doc, "after")
        for record in event_records(value)
        if record_id(record)
    }
    assert not (changed_ids & forbidden), "the receipt also presents a decoy or another series occurrence as updated"
    scope = first_value(doc, "scope")
    if scope is not None:
        assert norm(scope) not in {"series", "entireseries", "alloccurrences"}, (
            "the declared update scope would modify the whole recurring series"
        )


def test_requested_time_transition():
    """Criterion: time_transition."""
    doc = load_output()
    request, _, target = source()
    before = find_state_event(doc, "before", target["id"])
    after = find_state_event(doc, "after", target["id"])
    before_interval = interval(before)
    after_interval = interval(after)
    assert before_interval is not None, "the completed receipt lacks a usable pre-change interval"
    assert after_interval is not None, "the completed receipt lacks a usable updated interval"
    source_start = datetime.fromisoformat(target["start"]["dateTime"])
    source_end = datetime.fromisoformat(target["end"]["dateTime"])
    assert before_interval[0] == source_start and before_interval[1] == source_end, (
        "the receipt's pre-change interval does not match the selected source occurrence"
    )
    change = request["requested_change"]
    expected_start = datetime.fromisoformat(change["new_start_local"])
    expected_end = expected_start + timedelta(minutes=change["preserve_duration_minutes"])
    assert after_interval[0] == expected_start, "the occurrence was not moved to the requested Pacific start instant"
    assert after_interval[1] == expected_end, "the updated end time does not preserve the requested 75-minute duration"
    assert after_interval[1] - after_interval[0] == source_end - source_start, (
        "the meeting duration changed during rescheduling"
    )
    assert isinstance(after, dict)
    assert timezone_name(field(after, "start")) == change["time_zone"], (
        "the updated start is not labelled with the requested IANA timezone"
    )
    assert timezone_name(field(after, "end")) == change["time_zone"], (
        "the updated end is not labelled with the requested IANA timezone"
    )


def test_non_time_details_preserved():
    """Criterion: detail_preservation."""
    doc = load_output()
    _, _, target = source()
    after = find_state_event(doc, "after", target["id"])
    assert isinstance(after, dict), "the updated event cannot be inspected for preserved meeting details"
    normalized_after = {norm(key): value for key, value in after.items()}
    fields = [
        "summary",
        "status",
        "organizer",
        "attendees",
        "location",
        "description",
        "conferenceData",
        "reminders",
        "visibility",
        "recurringEventId",
        "originalStartTime",
    ]
    missing = [name for name in fields if norm(name) not in normalized_after]
    assert not missing, f"the update receipt omits preserved meeting details: {', '.join(missing)}"
    changed = [
        name
        for name in fields
        if comparable(normalized_after[norm(name)]) != comparable(target[name])
    ]
    assert not changed, f"non-time meeting details changed or became inconsistent: {', '.join(changed)}"


def test_all_attendees_notified_without_extras():
    """Criterion: notification_dispatch."""
    doc = load_output()
    _, _, target = source()
    mode = first_value(doc, "send_updates")
    assert mode is not None and norm(mode) in {"all", "allattendees", "everyone", "allguests"}, (
        "the completed update does not request notifications for all attendees"
    )
    expected = {attendee["email"].lower() for attendee in target["attendees"]}
    sections = section_values(doc, "notifications")
    if sections:
        actual = set().union(*(emails(section) for section in sections))
        assert actual == expected, (
            f"notification recipients differ from the current attendee set; missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )
    after = find_state_event(doc, "after", target["id"])
    assert isinstance(after, dict)
    assert emails(field(after, "attendees")) == expected, (
        "the updated event adds or removes invitees, so sendUpdates=all would reach the wrong set"
    )
