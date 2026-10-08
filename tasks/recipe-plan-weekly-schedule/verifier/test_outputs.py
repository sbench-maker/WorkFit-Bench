from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT_PATH = RESULTS_DIR / "output.json"


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


SECTION_ALIASES = {
    "gaps": {"usablegaps", "freewindows", "availability", "availableslots", "openwindows", "openslots", "candidatewindows"},
    "proposals": {"proposedevents", "proposedadditions", "additions", "newevents", "scheduledblocks", "eventstoadd", "focusblocks"},
    "agenda": {"agenda", "updatedagenda", "updatedworkweekagenda", "resultingagenda", "finalagenda", "workweekagenda", "updatedschedule", "finalschedule"},
    "rationale": {"rationale", "fitnote", "reasoning", "explanation", "planningnote", "notes", "summary"},
}

FIELD_ALIASES = {
    "id": {"id", "eventid", "eventidentifier", "uid"},
    "title": {"summary", "title", "name", "event", "label"},
    "date": {"date", "day", "localdate"},
    "start": {"start", "starttime", "begin", "begins", "from"},
    "end": {"end", "endtime", "finish", "finishes", "to"},
    "status": {"status", "eventstatus", "state"},
    "all_day": {"allday", "isallday"},
}


def walk(value: object):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def load_output() -> object:
    assert OUTPUT_PATH.is_file(), "output.json is missing, so the proposed calendar update cannot be reviewed"
    try:
        value = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        pytest.fail(f"output.json is not readable JSON: {exc}")
    assert isinstance(value, (dict, list)), "output.json must contain a JSON object or list"
    return value


def load_output_optional() -> object | None:
    if not OUTPUT_PATH.is_file():
        return None
    try:
        value = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, (dict, list)) else None


def source_data() -> tuple[dict, dict]:
    calendar = json.loads((DATA_DIR / "calendar_export.json").read_text(encoding="utf-8"))
    policy = json.loads((DATA_DIR / "planning_preferences.json").read_text(encoding="utf-8"))
    return calendar, policy


def find_sections(doc: object, section: str) -> list[object]:
    aliases = SECTION_ALIASES[section]
    matches: list[object] = []
    for node in walk(doc):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            if norm(key) in aliases:
                matches.append(value)
    return matches


def get_field(record: dict, field: str) -> object | None:
    for key, value in record.items():
        if norm(key) in FIELD_ALIASES[field]:
            return value
    return None


def looks_like_interval(record: dict) -> bool:
    keys = {norm(key) for key in record}
    return bool(keys & FIELD_ALIASES["start"]) and bool(keys & FIELD_ALIASES["end"])


def records_from_sections(doc: object, section: str) -> list[dict]:
    records: list[dict] = []
    seen: set[int] = set()

    def collect(node: object, day: object | None = None) -> None:
        if isinstance(node, list):
            for item in node:
                collect(item, day)
            return
        if not isinstance(node, dict):
            return
        current_day = get_field(node, "date") or day
        if id(node) not in seen:
            if looks_like_interval(node):
                record = dict(node)
                if get_field(record, "date") is None and current_day is not None:
                    record["date"] = current_day
                records.append(record)
                seen.add(id(node))
            else:
                # A day-grouped agenda may use one human-readable time range per entry.
                raw_time = next((value for key, value in node.items() if norm(key) == "time"), None)
                match = re.fullmatch(r"\s*(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\s*", raw_time) if isinstance(raw_time, str) else None
                if match and current_day is not None:
                    records.append({**node, "date": current_day, "start": match.group(1), "end": match.group(2)})
                    seen.add(id(node))
        for value in node.values():
            collect(value, current_day)

    for payload in find_sections(doc, section):
        collect(payload)
    return records


def parse_datetime(value: object, timezone: ZoneInfo, *, day_value: object | None = None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", raw):
            if not isinstance(day_value, str):
                return None
            parsed_time = time.fromisoformat(raw)
            return datetime.combine(date.fromisoformat(day_value[:10]), parsed_time, timezone)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            return datetime.combine(date.fromisoformat(raw), time(), timezone)
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone)
        return parsed.astimezone(timezone)
    except ValueError:
        return None


def parse_interval(record: dict, timezone: ZoneInfo) -> tuple[datetime, datetime] | None:
    day_value = get_field(record, "date")
    start = parse_datetime(get_field(record, "start"), timezone, day_value=day_value)
    end = parse_datetime(get_field(record, "end"), timezone, day_value=day_value)
    if start is None or end is None:
        return None
    if end <= start and isinstance(get_field(record, "end"), str) and "T" not in str(get_field(record, "end")):
        end += timedelta(days=1)
    return (start, end) if end > start else None


def at(day: date, hhmm: str, timezone: ZoneInfo) -> datetime:
    hour, minute = (int(part) for part in hhmm.split(":"))
    return datetime.combine(day, time(hour, minute), timezone)


def overlaps(start: datetime, end: datetime, other_start: datetime, other_end: datetime) -> bool:
    return start < other_end and end > other_start


def merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged: list[list[datetime]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def expected_gaps() -> tuple[list[tuple[datetime, datetime]], dict, dict, ZoneInfo]:
    calendar, policy = source_data()
    timezone = ZoneInfo(policy["timezone"])
    first = date.fromisoformat(policy["target_week"]["start"])
    last = date.fromisoformat(policy["target_week"]["end"])
    duration = timedelta(minutes=policy["request"]["duration_minutes"])
    rules = policy["availability_rules"]
    before = timedelta(minutes=rules["buffer_before_minutes"])
    after = timedelta(minutes=rules["buffer_after_minutes"])
    gaps: list[tuple[datetime, datetime]] = []

    for offset in range((last - first).days + 1):
        day = first + timedelta(days=offset)
        day_name = day.strftime("%A")
        hours = policy["working_hours"].get(day_name)
        if not hours:
            continue
        work_start, work_end = at(day, hours["start"], timezone), at(day, hours["end"], timezone)
        blockers: list[tuple[datetime, datetime]] = []
        for event in calendar["events"]:
            if event.get("status") not in rules["blocking_statuses"]:
                continue
            if event.get("transparency") != rules["blocking_transparency"]:
                continue
            event_start = parse_datetime(event["start"], timezone)
            event_end = parse_datetime(event["end"], timezone)
            assert event_start and event_end
            if event.get("all_day"):
                blocked_start, blocked_end = event_start, event_end
            else:
                blocked_start, blocked_end = event_start - before, event_end + after
            if overlaps(work_start, work_end, blocked_start, blocked_end):
                blockers.append((max(work_start, blocked_start), min(work_end, blocked_end)))
        for protected in policy["protected_time"]:
            if day_name in protected["days"]:
                blockers.append((at(day, protected["start"], timezone), at(day, protected["end"], timezone)))

        cursor = work_start
        for busy_start, busy_end in merge_intervals(blockers):
            if busy_start - cursor >= duration:
                gaps.append((cursor, busy_start))
            cursor = max(cursor, busy_end)
        if work_end - cursor >= duration:
            gaps.append((cursor, work_end))
    return gaps, calendar, policy, timezone


def event_title(record: dict) -> str:
    value = get_field(record, "title")
    return str(value).strip() if value is not None else ""


def event_id(record: dict) -> str:
    value = get_field(record, "id")
    return str(value).strip() if value is not None else ""


def same_minute(left: datetime, right: datetime) -> bool:
    return abs((left - right).total_seconds()) < 60


def interval_inside(inner: tuple[datetime, datetime], outer: tuple[datetime, datetime]) -> bool:
    return inner[0] >= outer[0] and inner[1] <= outer[1]


def test_usable_gap_accuracy():
    """Criterion: gap_accuracy."""
    doc = load_output_optional()
    assert doc is not None, "usable gaps cannot be checked because output.json is unavailable or unreadable"
    expected, _, policy, timezone = expected_gaps()
    actual_records = records_from_sections(doc, "gaps")
    parsed = [parse_interval(record, timezone) for record in actual_records]
    assert actual_records and all(interval is not None for interval in parsed), (
        "each reported usable gap needs an interpretable start and end"
    )
    actual = [interval for interval in parsed if interval is not None]
    minimum = timedelta(minutes=policy["request"]["duration_minutes"])
    too_short = [interval for interval in actual if interval[1] - interval[0] < minimum]
    assert not too_short, "a reported gap is too short for one requested 75-minute block"
    outside = [interval for interval in actual if not any(interval_inside(interval, gap) for gap in expected)]
    assert not outside, "a reported gap overlaps protected, buffered, all-day, or out-of-hours time"
    missed = [gap for gap in expected if not any(interval_inside(interval, gap) for interval in actual)]
    assert not missed, f"{len(missed)} policy-compliant target-week gap(s) are missing"
    unique = {(interval[0], interval[1]) for interval in actual}
    assert len(unique) == len(actual), "the same usable gap is listed more than once"


def test_proposed_schedule_compliance():
    """Criterion: proposed_schedule."""
    doc = load_output_optional()
    assert doc is not None, "the proposed schedule cannot be checked because output.json is unavailable or unreadable"
    gaps, calendar, policy, timezone = expected_gaps()
    records = records_from_sections(doc, "proposals")
    request = policy["request"]
    assert len(records) == request["count"], f"expected {request['count']} proposed blocks, found {len(records)}"
    intervals = [parse_interval(record, timezone) for record in records]
    assert all(interval is not None for interval in intervals), "every proposed block needs an interpretable start and end"
    parsed = [interval for interval in intervals if interval is not None]
    problems: list[str] = []
    for index, (record, interval) in enumerate(zip(records, parsed), start=1):
        start, end = interval
        if norm(event_title(record)) != norm(request["summary"]):
            problems.append(f"block {index} is not titled {request['summary']!r}")
        if end - start != timedelta(minutes=request["duration_minutes"]):
            problems.append(f"block {index} is not {request['duration_minutes']} minutes")
        if start.minute % request["start_increment_minutes"] or start.second or start.microsecond:
            problems.append(f"block {index} does not begin on a {request['start_increment_minutes']}-minute boundary")
        if not any(interval_inside(interval, gap) for gap in gaps):
            problems.append(f"block {index} is not inside a usable gap")
    for index, left in enumerate(parsed):
        for right in parsed[index + 1:]:
            if overlaps(left[0], left[1], right[0], right[1]):
                problems.append("two proposed focus blocks overlap")
                break
    counts = Counter(start.date() for start, _ in parsed)
    if len(counts) < request["minimum_distinct_days"]:
        problems.append("the blocks do not span the minimum number of distinct workdays")
    if counts and max(counts.values()) > request["maximum_per_day"]:
        problems.append("the maximum number of focus blocks on one day is exceeded")
    assert not problems, "; ".join(problems)


def source_interval(event: dict, timezone: ZoneInfo) -> tuple[datetime, datetime]:
    start = parse_datetime(event["start"], timezone)
    end = parse_datetime(event["end"], timezone)
    assert start is not None and end is not None
    return start, end


def record_matches_event(record: dict, event: dict, timezone: ZoneInfo) -> bool:
    record_identifier = event_id(record)
    interval = parse_interval(record, timezone)
    identity_matches = (
        record_identifier == event["id"]
        if record_identifier
        else norm(event_title(record)) == norm(event["summary"])
    )
    if interval is None or not identity_matches:
        return False
    expected = source_interval(event, timezone)
    return same_minute(interval[0], expected[0]) and same_minute(interval[1], expected[1])


def record_matches_proposal(record: dict, proposal: dict, timezone: ZoneInfo) -> bool:
    if norm(event_title(record)) != norm(event_title(proposal)):
        return False
    left, right = parse_interval(record, timezone), parse_interval(proposal, timezone)
    return bool(left and right and same_minute(left[0], right[0]) and same_minute(left[1], right[1]))


def test_updated_agenda_state_transition():
    """Criterion: agenda_transition."""
    doc = load_output_optional()
    assert doc is not None, "the updated agenda cannot be checked because output.json is unavailable or unreadable"
    _, calendar, policy, timezone = expected_gaps()
    agenda = records_from_sections(doc, "agenda")
    proposals = records_from_sections(doc, "proposals")
    assert agenda, "the updated workweek agenda contains no identifiable events"
    first = datetime.combine(date.fromisoformat(policy["target_week"]["start"]), time(), timezone)
    last = datetime.combine(date.fromisoformat(policy["target_week"]["end"]) + timedelta(days=1), time(), timezone)
    expected_active = []
    cancelled = []
    for event in calendar["events"]:
        start, end = source_interval(event, timezone)
        if not overlaps(first, last, start, end):
            continue
        (cancelled if event["status"] == "cancelled" else expected_active).append(event)

    missing = []
    duplicated = []
    agenda_id_counts = Counter(event_id(record) for record in agenda if event_id(record))
    for event in expected_active:
        matches = [record for record in agenda if record_matches_event(record, event, timezone)]
        if not matches:
            missing.append(event["id"])
        elif len(matches) > 1 or agenda_id_counts[event["id"]] > 1:
            duplicated.append(event["id"])
    assert not missing, f"existing active workweek events were dropped or moved: {missing}"
    assert not duplicated, f"existing workweek events are duplicated in the updated agenda: {duplicated}"

    missing_proposals = [
        event_title(proposal) + "@" + str(get_field(proposal, "start"))
        for proposal in proposals
        if not any(record_matches_proposal(record, proposal, timezone) for record in agenda)
    ]
    assert not missing_proposals, f"proposed additions are absent from the updated agenda: {missing_proposals}"

    for event in cancelled:
        for record in agenda:
            if record_matches_event(record, event, timezone):
                status = norm(get_field(record, "status") or "")
                assert status in {"cancelled", "canceled"}, (
                    f"cancelled event {event['id']} is presented as an active agenda commitment"
                )
    outside = []
    for record in agenda:
        interval = parse_interval(record, timezone)
        if interval and not overlaps(first, last, interval[0], interval[1]):
            outside.append(event_id(record) or event_title(record))
    assert not outside, f"the workweek agenda includes events outside October 5–9: {outside[:5]}"
