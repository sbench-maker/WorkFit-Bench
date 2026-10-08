from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo


DATA_ROOT = Path(os.environ.get("TASK_DATA_ROOT", "/root/data"))
RESULTS_ROOT = Path(os.environ.get("TASK_RESULTS_ROOT", "/root/results"))
OUTPUT = RESULTS_ROOT / "call_plan.json"

CALL_LIST_KEYS = {
    "call_list", "calls", "ranked_leads", "lead_ranking", "priorities", "call_cards",
    "leads", "top_leads", "daily_calls",
}
DRAFT_LIST_KEYS = {
    "follow_up_drafts", "followup_drafts", "follow_ups", "followups", "email_drafts", "drafts",
    "followup_messages", "follow_up_messages",
}
CALENDAR_LIST_KEYS = {
    "calendar_proposals", "proposed_calendar_blocks", "proposed_calls", "call_slots", "calendar_blocks",
    "calendar", "schedule", "proposed_slots",
}
START_KEYS = {"start", "start_at", "start_time", "starts_at", "begin", "from"}
END_KEYS = {"end", "end_at", "end_time", "ends_at", "finish", "to"}


def norm_key(value: object) -> str:
    split_camel = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value).strip())
    return re.sub(r"[^a-z0-9]+", "_", split_camel.casefold()).strip("_")


def norm_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def csv_rows(name: str) -> list[dict[str, str]]:
    with (DATA_ROOT / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_inputs() -> dict:
    context = json.loads((DATA_ROOT / "run_context.json").read_text(encoding="utf-8"))
    policy = json.loads((DATA_ROOT / "call_policy.json").read_text(encoding="utf-8"))
    contacts = csv_rows("contacts.csv")
    return {
        "context": context,
        "policy": policy,
        "contacts": contacts,
        "contact_by_id": {row["contact_id"]: row for row in contacts},
        "deals": csv_rows("deals.csv"),
        "activities": csv_rows("activities.csv"),
        "emails": csv_rows("emails.csv"),
        "calendar": csv_rows("calendar_events.csv"),
    }


INPUTS = load_inputs()
TZ = ZoneInfo(INPUTS["context"]["owner_timezone"])
TARGET_DATE = datetime.fromisoformat(INPUTS["context"]["target_date"]).date()
SNAPSHOT = datetime.fromisoformat(INPUTS["context"]["snapshot_generated_at"])
if SNAPSHOT.tzinfo is None:
    SNAPSHOT = SNAPSHOT.replace(tzinfo=TZ)
else:
    SNAPSHOT = SNAPSHOT.astimezone(TZ)


def parse_dt(value: object, *, date_value: Optional[object] = None) -> Optional[datetime]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", raw):
        use_date = TARGET_DATE if date_value is None else datetime.fromisoformat(str(date_value)).date()
        parsed_time = time.fromisoformat(raw)
        return datetime.combine(use_date, parsed_time, TZ)
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed.replace(tzinfo=TZ) if parsed.tzinfo is None else parsed.astimezone(TZ)


def get_alias(mapping: dict, aliases: set[str]) -> Optional[object]:
    normalized = {norm_key(key): value for key, value in mapping.items()}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return None


def all_dicts(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from all_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_dicts(child)


def named_lists(value: object, aliases: set[str]) -> list[list]:
    found = []
    for mapping in all_dicts(value):
        for key, child in mapping.items():
            if norm_key(key) in aliases and isinstance(child, list):
                found.append(child)
    return found


def load_payload() -> tuple[Optional[object], Optional[str]]:
    if not OUTPUT.is_file():
        return None, f"missing requested artifact: {OUTPUT}"
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8")), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"call_plan.json is not readable JSON: {exc}"


def resolve_contact_id(mapping: dict) -> Optional[str]:
    candidates: list[object] = []
    for item in all_dicts(mapping):
        direct = get_alias(item, {"contact_id", "lead_id", "prospect_id", "crm_contact_id", "id"})
        if direct is not None:
            candidates.append(direct)
    valid_ids = INPUTS["contact_by_id"]
    for value in candidates:
        if str(value).strip().upper() in valid_ids:
            return str(value).strip().upper()

    flattened = " ".join(norm_text(value) for value in mapping.values() if not isinstance(value, (dict, list)))
    for contact_id, contact in valid_ids.items():
        full_name = norm_text(f"{contact['first_name']} {contact['last_name']}")
        if full_name and full_name in flattened:
            return contact_id
        if norm_text(contact["email"]) in flattened:
            return contact_id
    return None


def extract_call_cards(payload: object) -> list[dict]:
    for candidate in named_lists(payload, CALL_LIST_KEYS):
        rows = [item for item in candidate if isinstance(item, dict)]
        if rows:
            return rows
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return list(payload)
    ranked = []
    for mapping in all_dicts(payload):
        if get_alias(mapping, {"rank", "priority_rank", "position", "order"}) is not None and resolve_contact_id(mapping):
            ranked.append(mapping)
    return ranked


def ordered_contact_ids(cards: list[dict]) -> list[Optional[str]]:
    decorated = []
    explicit_ranks = True
    for index, card in enumerate(cards):
        raw_rank = get_alias(card, {"rank", "priority_rank", "position", "order"})
        try:
            rank = int(raw_rank)
        except (TypeError, ValueError):
            explicit_ranks = False
            rank = index + 1
        decorated.append((rank, index, resolve_contact_id(card)))
    if explicit_ranks:
        decorated.sort()
    return [contact_id for _, _, contact_id in decorated]


def expected_ranking() -> list[str]:
    policy = INPUTS["policy"]["scoring"]
    signal_points = policy["signal_points"]
    activity_by_contact: dict[str, list[dict]] = {}
    email_by_contact: dict[str, list[dict]] = {}
    for row in INPUTS["activities"]:
        item = dict(row)
        item["when"] = parse_dt(row["occurred_at"])
        activity_by_contact.setdefault(row["contact_id"], []).append(item)
    for row in INPUTS["emails"]:
        item = dict(row)
        item["when"] = parse_dt(row["sent_at"])
        email_by_contact.setdefault(row["contact_id"], []).append(item)

    scored = []
    contacts = INPUTS["contact_by_id"]
    for deal in INPUTS["deals"]:
        contact = contacts[deal["contact_id"]]
        if deal["status"] != "open" or contact["call_status"] != "call_allowed":
            continue
        activities = activity_by_contact.get(deal["contact_id"], [])
        if not any(item["when"] and 0 <= (TARGET_DATE - item["when"].date()).days <= 29 for item in activities):
            continue
        qualifying = [
            item for item in activities
            if item["when"] and item["activity_type"] in signal_points
            and timedelta(0) <= SNAPSHOT - item["when"] <= timedelta(days=policy["signal_lookback_days"])
        ]
        signal = max(qualifying, key=lambda item: item["when"]) if qualifying else None
        touch = parse_dt(deal["last_owner_touch_at"])
        score = (
            max(0, 30 - (TARGET_DATE - touch.date()).days)
            + policy["stage_points"][deal["stage"]]
            + (signal_points[signal["activity_type"]] if signal else 0)
            + min(25, int(deal["amount_usd"]) // 10000)
        )
        mail = sorted(email_by_contact.get(deal["contact_id"], []), key=lambda item: item["when"])
        unanswered = bool(mail and mail[-1]["direction"] == "inbound")
        scored.append((
            -score, -int(unanswered),
            -(signal["when"].timestamp() if signal else 0),
            -int(deal["amount_usd"]), deal["contact_id"],
        ))
    scored.sort()
    return [item[-1] for item in scored[: INPUTS["context"]["lead_count"]]]


def talking_points(card: dict) -> list[str]:
    value = get_alias(card, {"talking_points", "talk_track", "talking_points_and_questions", "points"})
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [line.strip(" -•\t") for line in value.splitlines() if line.strip(" -•\t")]
    return []


def call_goal(card: dict) -> str:
    value = get_alias(card, {"call_goal", "goal", "goal_for_this_call", "goal_for_call", "objective", "call_objective"})
    return str(value or "").strip()


def extract_calendar_entries(payload: object, cards: list[dict]) -> list[dict]:
    entries: list[dict] = []
    seen: set[int] = set()
    for candidate in named_lists(payload, CALENDAR_LIST_KEYS):
        for item in candidate:
            if isinstance(item, dict) and id(item) not in seen:
                entries.append(item)
                seen.add(id(item))
    nested_keys = {"proposed_calendar", "calendar_proposal", "calendar_block", "proposed_slot", "call_slot", "slot"}
    for card in cards:
        for mapping in all_dicts(card):
            for key, child in mapping.items():
                if norm_key(key) in nested_keys and isinstance(child, dict) and id(child) not in seen:
                    merged = dict(child)
                    if resolve_contact_id(merged) is None:
                        merged["_inherited_contact_id"] = resolve_contact_id(card)
                    entries.append(merged)
                    seen.add(id(child))
    return entries


def entry_contact_id(entry: dict) -> Optional[str]:
    inherited = entry.get("_inherited_contact_id")
    return str(inherited) if inherited else resolve_contact_id(entry)


def entry_interval(entry: dict) -> tuple[Optional[datetime], Optional[datetime]]:
    date_value = get_alias(entry, {"date", "target_date", "day"})
    start = parse_dt(get_alias(entry, START_KEYS), date_value=date_value)
    end = parse_dt(get_alias(entry, END_KEYS), date_value=date_value)
    if start and end is None:
        duration = get_alias(entry, {"duration_minutes", "minutes", "duration"})
        try:
            end = start + timedelta(minutes=int(duration))
        except (TypeError, ValueError):
            pass
    return start, end


def extract_drafts(payload: object, cards: list[dict]) -> tuple[list[dict], bool]:
    drafts: list[dict] = []
    found_collection = False
    seen: set[int] = set()
    for candidate in named_lists(payload, DRAFT_LIST_KEYS):
        found_collection = True
        for item in candidate:
            if isinstance(item, dict) and id(item) not in seen:
                drafts.append(item)
                seen.add(id(item))
    nested_keys = {"follow_up_draft", "followup_draft", "email_draft", "draft_message"}
    for card in cards:
        for mapping in all_dicts(card):
            for key, child in mapping.items():
                if norm_key(key) in nested_keys and isinstance(child, dict) and id(child) not in seen:
                    merged = dict(child)
                    if resolve_contact_id(merged) is None:
                        merged["_inherited_contact_id"] = resolve_contact_id(card)
                    drafts.append(merged)
                    seen.add(id(child))
                    found_collection = True
    return drafts, found_collection


def draft_contact_id(draft: dict) -> Optional[str]:
    inherited = draft.get("_inherited_contact_id")
    return str(inherited) if inherited else resolve_contact_id(draft)


def draft_message_parts(draft: dict) -> tuple[str, str, str]:
    subject = str(get_alias(draft, {"subject", "email_subject", "thread_subject"}) or "").strip()
    body = str(get_alias(draft, {"body", "message", "content", "draft_body"}) or "").strip()
    thread = str(get_alias(draft, {"thread_id", "email_thread_id", "conversation_id"}) or "").strip()
    combined = get_alias(draft, {"draft", "email", "email_draft", "draft_text", "full_message"})
    if isinstance(combined, str) and combined.strip():
        if not subject:
            match = re.search(r"(?im)^\s*subject\s*:\s*(.+?)\s*$", combined)
            subject = match.group(1).strip() if match else ""
        if not thread:
            match = re.search(r"(?im)^\s*(?:thread|conversation)(?:_id| id)?\s*:\s*(.+?)\s*$", combined)
            thread = match.group(1).strip() if match else ""
        if not body:
            body = re.sub(r"(?im)^\s*(?:subject|thread|conversation)(?:_id| id)?\s*:\s*.*$", "", combined).strip()
    return subject, body, thread


def expected_due_drafts(selected_ids: set[str]) -> set[str]:
    messages: dict[tuple[str, str], list[dict]] = {}
    for row in INPUTS["emails"]:
        item = dict(row)
        item["when"] = parse_dt(row["sent_at"])
        messages.setdefault((row["contact_id"], row["thread_id"]), []).append(item)
    due = set()
    for (contact_id, _), thread in messages.items():
        latest = max(thread, key=lambda item: item["when"])
        if contact_id in selected_ids and latest["direction"] == "inbound" and SNAPSHOT - latest["when"] > timedelta(days=3):
            due.add(contact_id)
    return due


def represents_no_action(value: object) -> bool:
    if value is None or value is False:
        return True
    if isinstance(value, str):
        return norm_key(value) in {"", "none", "no", "not_applicable", "not_performed", "no_changes"}
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    if isinstance(value, dict):
        if not value:
            return True
        return all(
            norm_key(key) in {"status", "state", "performed", "executed", "count"}
            and (represents_no_action(child) or child == 0)
            for key, child in value.items()
        )
    return False


def test_selected_leads_and_rank_order():
    payload, _ = load_payload()
    cards = extract_call_cards(payload) if payload is not None else []
    actual = ordered_contact_ids(cards)
    expected = expected_ranking()
    assert actual == expected, (
        f"ranked contacts are {actual}, expected {expected}; the owner would spend call time on the wrong leads"
    )


def test_calendar_proposals_are_feasible():
    payload, _ = load_payload()
    cards = extract_call_cards(payload) if payload is not None else []
    entries = extract_calendar_entries(payload, cards)
    selected = set(expected_ranking())
    assert len(entries) == 5, f"expected one proposed block per selected lead, found {len(entries)}"
    entry_ids = [entry_contact_id(entry) for entry in entries]
    assert set(entry_ids) == selected and len(entry_ids) == len(set(entry_ids)), (
        "calendar proposals must cover each selected contact exactly once"
    )

    windows = [
        (
            datetime.combine(TARGET_DATE, time.fromisoformat(start), TZ),
            datetime.combine(TARGET_DATE, time.fromisoformat(end), TZ),
        )
        for start, end in INPUTS["policy"]["calendar"]["working_windows"]
    ]
    busy = [
        (parse_dt(row["start_at"]), parse_dt(row["end_at"]))
        for row in INPUTS["calendar"]
        if row["owner_id"] == INPUTS["context"]["owner_id"] and row["status"] == "busy"
        and parse_dt(row["start_at"]).date() == TARGET_DATE
    ]
    intervals = []
    for entry in entries:
        start, end = entry_interval(entry)
        assert start and end, f"calendar proposal for {entry_contact_id(entry)} lacks usable start/end times"
        assert start.date() == TARGET_DATE and end - start == timedelta(minutes=20), (
            f"calendar proposal for {entry_contact_id(entry)} must be a 20-minute block on the target date"
        )
        assert any(start >= window_start and end <= window_end for window_start, window_end in windows), (
            f"calendar proposal for {entry_contact_id(entry)} is outside a working window"
        )
        assert not any(start < busy_end and end > busy_start for busy_start, busy_end in busy), (
            f"calendar proposal for {entry_contact_id(entry)} overlaps a frozen busy event"
        )
        intervals.append((start, end, entry_contact_id(entry)))
    for index, (start, end, contact_id) in enumerate(intervals):
        for other_start, other_end, other_id in intervals[index + 1:]:
            assert not (start < other_end and end > other_start), (
                f"proposed calls for {contact_id} and {other_id} overlap"
            )


def test_follow_up_scope_and_nonexecution():
    payload, _ = load_payload()
    cards = extract_call_cards(payload) if payload is not None else []
    drafts, _ = extract_drafts(payload, cards)
    expected = expected_due_drafts(set(expected_ranking()))
    actual = [draft_contact_id(draft) for draft in drafts]
    assert set(actual) == expected and len(actual) == len(set(actual)), (
        f"draft recipients are {actual}, expected exactly {sorted(expected)} from unanswered-thread timing"
    )
    for draft in drafts:
        subject, body, thread = draft_message_parts(draft)
        assert (subject or thread) and body, (
            f"follow-up draft for {draft_contact_id(draft)} needs a message body and thread or subject context"
        )

    forbidden_states = {"sent", "delivered", "created", "scheduled", "confirmed", "executed", "completed"}
    for mapping in all_dicts(payload):
        for key, value in mapping.items():
            normalized_key = norm_key(key)
            if normalized_key in {"status", "state", "delivery_status", "action_status"}:
                assert norm_key(value) not in forbidden_states, (
                    f"artifact marks an action as {value!r}; all messages and events must remain drafts/proposals"
                )
            if normalized_key in {"actions_performed", "executed_actions", "sent_messages", "created_events"}:
                assert represents_no_action(value), (
                    f"artifact reports executed action data in {key!r}"
                )
            if normalized_key in {"crm_changes", "crm_updates", "deal_stage_updates"}:
                assert represents_no_action(value), (
                    "artifact reports a CRM change even though the task permits none"
                )
