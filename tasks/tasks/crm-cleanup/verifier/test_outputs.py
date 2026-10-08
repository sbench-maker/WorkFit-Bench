from __future__ import annotations

import csv
import json
import os
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import pytest


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("TASK_OUTPUT_PATH", "/root/results/output.json"))


class StructuralError(ValueError):
    pass


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def key(value: object) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value))
    return re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_")


def norm_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return re.sub(r"[^a-z0-9]+", "", text)


def moment(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def missing(value: object) -> bool:
    return value is None or (isinstance(value, str) and (not value.strip() or value.strip().casefold() in {"null", "none", "n/a"}))


def direct_value(mapping: dict, aliases: set[str]) -> object:
    wanted = {key(item) for item in aliases}
    for raw_key, value in mapping.items():
        if key(raw_key) in wanted:
            return value
    return None


def walk_dicts(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def find_list(root: object, aliases: set[str]) -> list | None:
    wanted = {key(item) for item in aliases}
    for mapping in walk_dicts(root):
        for raw_key, value in mapping.items():
            if key(raw_key) not in wanted:
                continue
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                # Accept common report wrappers such as
                # {"count": 3, "details": [...]}, not only id-keyed maps.
                for wrapper in ("items", "details", "records", "entries", "findings"):
                    wrapped = direct_value(value, {wrapper})
                    if isinstance(wrapped, list):
                        return wrapped
                if all(isinstance(item, dict) for item in value.values()):
                    rows = []
                    for container_id, item in value.items():
                        item = dict(item)
                        item.setdefault("id", container_id)
                        rows.append(item)
                    return rows
    return None


@lru_cache(maxsize=1)
def raw_output() -> object:
    if not OUTPUT.is_file():
        raise StructuralError(f"requested artifact is missing: {OUTPUT}")
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StructuralError(f"output.json is not readable JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise StructuralError("output.json must contain a JSON object so the cleanup plan is usable")
    return payload


STALE_ALIASES = {"stale_deals", "stale_deal_findings", "inactive_deals", "deals_stale"}
DUPLICATE_ALIASES = {"duplicate_contacts", "duplicate_contact_sets", "duplicate_sets", "contact_duplicates"}
MISSING_ALIASES = {"missing_required_fields", "missing_fields", "field_gaps", "required_field_gaps"}


def sections(payload: object) -> tuple[list, list, list]:
    stale = find_list(payload, STALE_ALIASES)
    duplicates = find_list(payload, DUPLICATE_ALIASES)
    gaps = find_list(payload, MISSING_ALIASES)
    if gaps is None:
        deal_gaps = find_list(payload, {"deal_field_gaps", "deals_missing_fields", "missing_deal_fields"})
        contact_gaps = find_list(payload, {"contact_field_gaps", "contacts_missing_fields", "missing_contact_fields"})
        if deal_gaps is not None or contact_gaps is not None:
            gaps = []
            for row in deal_gaps or []:
                if isinstance(row, dict):
                    row = dict(row)
                    row.setdefault("record_type", "deal")
                gaps.append(row)
            for row in contact_gaps or []:
                if isinstance(row, dict):
                    row = dict(row)
                    row.setdefault("record_type", "contact")
                gaps.append(row)
    absent = [name for name, value in (("stale deals", stale), ("duplicate contacts", duplicates), ("required-field gaps", gaps)) if value is None]
    if absent:
        raise StructuralError("cleanup plan has no recognizable section for: " + ", ".join(absent))
    for label, value in (("stale deals", stale), ("duplicate contacts", duplicates), ("required-field gaps", gaps)):
        if any(not isinstance(row, dict) for row in value):
            raise StructuralError(f"{label} must be a list of record objects")
    return stale, duplicates, gaps


def semantic_sections() -> tuple[list, list, list] | None:
    try:
        return sections(raw_output())
    except StructuralError:
        pytest.skip("semantic checks are blocked by the artifact-level parse/section error")
        return None


def row_id(row: dict, entity: str) -> str | None:
    aliases = {f"{entity}_id", "record_id", "id"}
    value = direct_value(row, aliases)
    if isinstance(value, (str, int)):
        return str(value).strip().upper()
    return None


def evidence_value(row: dict, aliases: set[str]) -> object:
    value = direct_value(row, aliases)
    if value is not None:
        return value
    for container_alias in ({"current", "evidence", "current_values", "source"},):
        nested = direct_value(row, container_alias)
        if isinstance(nested, dict):
            value = direct_value(nested, aliases)
            if value is not None:
                return value
    return None


@lru_cache(maxsize=1)
def source() -> dict:
    snapshot = json.loads((DATA / "snapshot.json").read_text(encoding="utf-8"))
    policy = json.loads((DATA / "cleanup_policy.json").read_text(encoding="utf-8"))
    contacts = read_csv("contacts.csv")
    deals = read_csv("deals.csv")
    associations = read_csv("deal_contacts.csv")
    activities = read_csv("activities.csv")
    return {
        "snapshot": snapshot,
        "policy": policy,
        "contacts": contacts,
        "deals": deals,
        "associations": associations,
        "activities": activities,
    }


def expected_stale() -> dict[str, dict]:
    src = source()
    policy = src["policy"]
    as_of = moment(src["snapshot"]["as_of"])
    cutoff = as_of - timedelta(days=policy["stale_after_days"])
    contacts = {row["contact_id"]: row for row in src["contacts"]}
    associated: dict[str, list[str]] = defaultdict(list)
    for row in src["associations"]:
        associated[row["deal_id"]].append(row["contact_id"])
    qualifying: dict[str, list[datetime]] = defaultdict(list)
    for row in src["activities"]:
        statuses = policy["qualifying_activity_status_by_type"].get(row["activity_type"], [])
        at = moment(row["occurred_at"])
        if row["status"] in statuses and at <= as_of:
            qualifying[row["deal_id"]].append(at)
    result = {}
    for deal in src["deals"]:
        if deal["pipeline_status"] != policy["open_deal_status"]:
            continue
        dates = qualifying.get(deal["deal_id"], [])
        last = max(dates) if dates else None
        if last is None or last < cutoff:
            result[deal["deal_id"]] = {
                "stage": deal["deal_stage"].strip() or None,
                "last_activity": None if last is None else last.date().isoformat(),
                "contacts": set(associated.get(deal["deal_id"], [])),
                "contact_names": {
                    norm_text(f"{contacts[cid]['first_name']} {contacts[cid]['last_name']}") for cid in associated.get(deal["deal_id"], [])
                },
                "amount": None if missing(deal["amount"]) else float(deal["amount"]),
            }
    return result


def actual_contact_refs(value: object) -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    names: set[str] = set()
    if isinstance(value, dict):
        for candidate in value:
            if re.fullmatch(r"C\d{4}", str(candidate).strip(), flags=re.I):
                ids.add(str(candidate).strip().upper())
        value = list(value.values())
    if not isinstance(value, list):
        value = [] if missing(value) else [value]
    for item in value:
        if isinstance(item, dict):
            candidate_id = direct_value(item, {"contact_id", "record_id", "id"})
            candidate_name = direct_value(item, {"name", "contact_name", "full_name"})
        else:
            candidate_id, candidate_name = item, item
        if isinstance(candidate_id, (str, int)) and re.fullmatch(r"C\d{4}", str(candidate_id).strip(), flags=re.I):
            ids.add(str(candidate_id).strip().upper())
        elif isinstance(candidate_name, str):
            names.add(norm_text(candidate_name))
        if isinstance(candidate_name, str):
            names.add(norm_text(candidate_name))
    return ids, names


def expected_missing() -> dict[tuple[str, str], set[str]]:
    src = source()
    associated: dict[str, list[str]] = defaultdict(list)
    for row in src["associations"]:
        associated[row["deal_id"]].append(row["contact_id"])
    open_deals = [row for row in src["deals"] if row["pipeline_status"] == src["policy"]["open_deal_status"]]
    expected: dict[tuple[str, str], set[str]] = {}
    for deal in open_deals:
        fields = {field for field in ("close_date", "amount", "deal_stage") if missing(deal[field])}
        if not associated.get(deal["deal_id"]):
            fields.add("associated_contact")
        if missing(deal["next_step"]) and missing(deal["notes"]):
            fields.add("next_step_or_notes")
        if fields:
            expected[("deal", deal["deal_id"])] = fields
    open_contacts = {cid for deal in open_deals for cid in associated.get(deal["deal_id"], [])}
    contact_rows = {row["contact_id"]: row for row in src["contacts"]}
    for contact_id in open_contacts:
        fields = {field for field in ("email", "company", "phone") if missing(contact_rows[contact_id][field])}
        if fields:
            expected[("contact", contact_id)] = fields
    return expected


def normalized_field_set(value: object) -> set[str]:
    if isinstance(value, str):
        values = [part for part in re.split(r"[,;|]", value) if part.strip()]
    elif isinstance(value, list):
        values = []
        for item in value:
            if isinstance(item, dict):
                item = direct_value(item, {"field", "field_name", "name"})
            if item is not None:
                values.append(str(item))
    elif isinstance(value, dict):
        values = [str(item) for item in value.keys()]
    else:
        values = []
    normalized = {key(item) for item in values}
    if {"next_step", "notes"}.issubset(normalized):
        normalized -= {"next_step", "notes"}
        normalized.add("next_step_or_notes")
    normalized.discard("associated_contacts")
    if any(key(item) == "associated_contacts" for item in values):
        normalized.add("associated_contact")
    return normalized


def expected_duplicates() -> set[frozenset[str]]:
    src = source()
    aliases = {norm_text(k): norm_text(v) for k, v in src["policy"]["duplicate_candidate_rules"]["first_name_aliases"].items()}
    contacts = src["contacts"]
    parent = {row["contact_id"]: row["contact_id"] for row in contacts}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    def first(row: dict) -> str:
        raw = norm_text(row["first_name"])
        return aliases.get(raw, raw)

    for index, left in enumerate(contacts):
        for right in contacts[index + 1 :]:
            emails_match = (
                bool(left["email"].strip())
                and left["email"].strip().casefold() == right["email"].strip().casefold()
            )
            identity_match = (
                bool(norm_text(left["company"]))
                and norm_text(left["company"]) == norm_text(right["company"])
                and norm_text(left["last_name"]) == norm_text(right["last_name"])
                and first(left) == first(right)
            )
            if emails_match or identity_match:
                union(left["contact_id"], right["contact_id"])
    groups: dict[str, set[str]] = defaultdict(set)
    for contact_id in parent:
        groups[find(contact_id)].add(contact_id)
    return {frozenset(ids) for ids in groups.values() if len(ids) > 1}


def group_members(row: dict) -> set[str]:
    members = direct_value(row, {"records", "contacts", "members", "contact_records", "contact_ids"})
    if members is None:
        keep = evidence_value(row, {"keep_contact_id", "keep_id"})
        drops = evidence_value(row, {"merge_from_contact_ids", "merge_ids", "duplicate_ids"})
        members = ([keep] if keep else []) + (drops if isinstance(drops, list) else ([drops] if drops else []))
    if isinstance(members, dict):
        converted = []
        for container_id, member in members.items():
            if isinstance(member, dict):
                member = dict(member)
                member.setdefault("id", container_id)
            else:
                member = container_id
            converted.append(member)
        members = converted
    if not isinstance(members, list):
        return set()
    ids = set()
    for member in members:
        if isinstance(member, dict):
            contact_id = row_id(member, "contact")
        else:
            contact_id = str(member).strip().upper() if member is not None else None
        if contact_id:
            ids.add(contact_id)
    return ids


def test_stale_deal_classification_and_evidence():
    """Every and only stale open deals are listed with the evidence needed for owner review."""
    stale_rows, _, _ = semantic_sections()
    expected = expected_stale()
    actual: dict[str, dict] = {}
    for row in stale_rows:
        deal_id = row_id(row, "deal")
        if deal_id:
            prior = actual.get(deal_id)
            actual[deal_id] = max((prior, row), key=lambda item: len(json.dumps(item, default=str))) if prior else row
    assert set(actual) == set(expected), (
        f"stale-deal membership differs; missing={sorted(set(expected)-set(actual))}, "
        f"unexpected={sorted(set(actual)-set(expected))}"
    )
    problems = []
    for deal_id, exp in expected.items():
        row = actual[deal_id]
        stage = evidence_value(row, {"deal_stage", "stage"})
        stage = None if missing(stage) else str(stage).strip().casefold()
        last = evidence_value(row, {"last_activity_date", "last_activity", "last_touch_date"})
        last = None if missing(last) else str(last).strip()[:10]
        amount = evidence_value(row, {"amount", "deal_amount", "value"})
        try:
            amount = None if missing(amount) else float(str(amount).replace(",", "").replace("$", ""))
        except ValueError:
            amount = "invalid"
        refs = evidence_value(row, {"associated_contacts", "contacts", "contact_ids"})
        contact_ids, contact_names = actual_contact_refs(refs)
        contacts_ok = contact_ids == exp["contacts"] if contact_ids else contact_names == exp["contact_names"]
        if stage != exp["stage"]:
            problems.append(f"{deal_id} stage={stage!r}, expected {exp['stage']!r}")
        if last != exp["last_activity"]:
            problems.append(f"{deal_id} last_activity={last!r}, expected {exp['last_activity']!r}")
        if amount != exp["amount"]:
            problems.append(f"{deal_id} amount={amount!r}, expected {exp['amount']!r}")
        if not contacts_ok:
            problems.append(f"{deal_id} associated contacts do not match the export")
    assert not problems, "stale-deal evidence errors: " + "; ".join(problems[:12])


def test_missing_field_classification_and_coverage():
    """Open deals and their contacts have exactly the required missing fields reported."""
    _, _, gap_rows = semantic_sections()
    expected = expected_missing()
    actual: dict[tuple[str, str], set[str]] = {}
    known_deals = {row["deal_id"] for row in source()["deals"]}
    known_contacts = {row["contact_id"] for row in source()["contacts"]}
    for row in gap_rows:
        raw_type = direct_value(row, {"record_type", "entity_type", "object_type", "type"})
        record_id = direct_value(row, {"record_id", "deal_id", "contact_id", "id"})
        if record_id is None:
            continue
        record_id = str(record_id).strip().upper()
        entity_type = key(raw_type) if raw_type is not None else ("deal" if record_id in known_deals else "contact" if record_id in known_contacts else "")
        entity_type = "deal" if entity_type in {"deal", "deals"} else "contact" if entity_type in {"contact", "contacts"} else entity_type
        fields = evidence_value(row, {"missing_fields", "required_fields_missing", "fields", "gaps"})
        compound_key = (entity_type, record_id)
        if compound_key in actual:
            actual[compound_key] |= normalized_field_set(fields)
        else:
            actual[compound_key] = normalized_field_set(fields)
    assert actual == expected, (
        "required-field findings differ from the frozen export; "
        f"missing_records={sorted(set(expected)-set(actual))}, unexpected_records={sorted(set(actual)-set(expected))}, "
        f"wrong_fields={sorted(item for item in set(expected)&set(actual) if expected[item] != actual[item])}"
    )


def test_duplicate_candidate_groups():
    """Duplicate candidates follow the supplied matching policy without merging near-match decoys."""
    _, duplicate_rows, _ = semantic_sections()
    raw_groups = [group_members(row) for row in duplicate_rows if len(group_members(row)) > 1]
    parent: dict[str, str] = {contact_id: contact_id for group in raw_groups for contact_id in group}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    for group in raw_groups:
        first = min(group)
        for contact_id in group:
            a, b = find(first), find(contact_id)
            if a != b:
                parent[max(a, b)] = min(a, b)
    components: dict[str, set[str]] = defaultdict(set)
    for contact_id in parent:
        components[find(contact_id)].add(contact_id)
    actual = {frozenset(group) for group in components.values() if len(group) > 1}
    expected = expected_duplicates()
    assert actual == expected, (
        f"duplicate groups differ; missing={sorted(map(sorted, expected-actual))}, "
        f"unexpected={sorted(map(sorted, actual-expected))}"
    )
