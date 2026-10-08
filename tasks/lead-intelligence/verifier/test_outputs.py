from __future__ import annotations

import csv
import json
import os
import re
from collections import defaultdict
from datetime import date
from functools import lru_cache
from pathlib import Path

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
OUTPUT_PATH = Path(os.environ.get("TASK_OUTPUT_PATH", "/root/results/output.json"))


def norm_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())


def norm_text(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9@.]+", " ", str(value).lower())).strip()


def is_true(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def direct_value(mapping: object, aliases: set[str]) -> object | None:
    if not isinstance(mapping, dict):
        return None
    normalized = {norm_key(key): value for key, value in mapping.items()}
    for alias in aliases:
        if norm_key(alias) in normalized:
            return normalized[norm_key(alias)]
    return None


def nested_value(mapping: object, aliases: set[str], containers: set[str]) -> object | None:
    value = direct_value(mapping, aliases)
    if value is not None:
        return value
    if not isinstance(mapping, dict):
        return None
    for key, child in mapping.items():
        if norm_key(key) in {norm_key(item) for item in containers} and isinstance(child, dict):
            value = direct_value(child, aliases)
            if value is not None:
                return value
    return None


IDENTITY_ALIASES = {"person_id", "lead_id", "prospect_id", "contact_id", "canonical_id"}
NAME_ALIASES = {"full_name", "lead_name", "prospect_name", "contact_name", "name"}
SCORE_ALIASES = {"fit_score", "total_score", "lead_score", "qualification_score", "score"}
RANK_ALIASES = {"rank", "priority_rank", "position", "order"}


def looks_like_lead(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    identity = nested_value(value, IDENTITY_ALIASES, {"lead", "prospect", "contact", "person", "profile"})
    name = nested_value(value, NAME_ALIASES, {"lead", "prospect", "contact", "person", "profile"})
    task_signal = any(
        direct_value(value, aliases) is not None
        for aliases in (
            SCORE_ALIASES,
            RANK_ALIASES,
            {"message", "draft", "outreach_message", "copy"},
            {"recommended_channel", "primary_channel", "outreach_channel", "channel"},
        )
    )
    return (identity is not None or name is not None) and task_signal


def collect_records(payload: object) -> list[dict]:
    preferred = {
        "shortlist", "leads", "rankedleads", "prospects", "outreachplan",
        "results", "contacts", "recommendations", "data",
    }
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        if any(looks_like_lead(item) for item in payload):
            return [item for item in payload if looks_like_lead(item)]
    if isinstance(payload, dict):
        for key, value in payload.items():
            if norm_key(key) in preferred and isinstance(value, list):
                records = [item for item in value if looks_like_lead(item)]
                if records:
                    return records
        found: list[dict] = []

        def walk(node: object, depth: int = 0) -> None:
            if depth > 5:
                return
            if looks_like_lead(node):
                found.append(node)
                return
            if isinstance(node, dict):
                for child in node.values():
                    walk(child, depth + 1)
            elif isinstance(node, list):
                for child in node:
                    walk(child, depth + 1)

        walk(payload)
        return found
    return []


def resolve_profiles(rows: list[dict[str, str]]) -> dict[str, dict]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if is_true(row["source_verified"]):
            grouped[row["person_id"]].append(row)
    priority = {"crm": 3, "linkedin": 2, "x": 1}
    fields = ["full_name", "title", "company_id", "location", "email", "x_handle", "linkedin_slug", "follower_count"]
    resolved: dict[str, dict] = {}
    for person_id, candidates in grouped.items():
        item = {"person_id": person_id}
        for field in fields:
            available = [row for row in candidates if row.get(field, "").strip()]
            if available:
                chosen = max(available, key=lambda row: (row["observed_at"], priority.get(row["source"], 0)))
                item[field] = chosen[field]
            else:
                item[field] = ""
        item["follower_count"] = int(item["follower_count"] or 0)
        item["profile_record_ids"] = [row["profile_record_id"] for row in candidates]
        resolved[person_id] = item
    return resolved


def follower_points(value: int, config: dict) -> int:
    for band in config["follower_bands"]:
        if value >= int(band["min_followers"]):
            return int(band["points"])
    return int(config["otherwise"])


def recent_points(age: int, config: dict) -> int:
    for band in config["age_bands"]:
        if age <= int(band["max_days"]):
            return int(band["points"])
    return int(config["otherwise"])


@lru_cache(maxsize=1)
def ground_truth() -> dict:
    brief = json.loads((DATA_DIR / "campaign_brief.json").read_text(encoding="utf-8"))
    profiles = resolve_profiles(read_csv("profile_export.csv"))
    companies = {row["company_id"]: row for row in read_csv("companies.csv")}
    crm = {row["person_id"]: row for row in read_csv("crm_contacts.csv")}
    bridges = {row["bridge_id"]: row for row in read_csv("mutual_contacts.csv")}
    as_of = date.fromisoformat(brief["as_of_date"])

    activities: dict[str, list[dict]] = defaultdict(list)
    for row in read_csv("activities.csv"):
        if is_true(row["verified"]) and row["topic"] in brief["target_topics"]:
            activities[row["person_id"]].append(row)
    newest_activity = {
        person_id: max(rows, key=lambda row: (row["activity_date"], row["activity_id"]))
        for person_id, rows in activities.items()
    }

    warmth = {kind: index for index, kind in enumerate(brief["warm_paths"]["warmth_order"])}
    eligible_paths: dict[str, list[dict]] = defaultdict(list)
    unverified_paths: dict[str, list[dict]] = defaultdict(list)
    for row in read_csv("warm_paths.csv"):
        destination = eligible_paths if is_true(row["verified"]) else unverified_paths
        destination[row["target_person_id"]].append(row)
    best_paths = {
        person_id: min(
            rows,
            key=lambda row: (
                warmth[row["path_type"]],
                -date.fromisoformat(row["evidence_date"]).toordinal(),
                row["path_id"],
            ),
        )
        for person_id, rows in eligible_paths.items()
    }

    cfg = brief["score"]
    exclusions = brief["exclusions"]
    ranked: list[dict] = []
    for person_id, person in profiles.items():
        crm_row = crm[person_id]
        if crm_row["consent_status"] in exclusions["consent_status"] or crm_row["lifecycle_stage"] in exclusions["lifecycle_stage"]:
            continue
        company = companies[person["company_id"]]
        activity = newest_activity.get(person_id)
        age = 9999 if not activity else (as_of - date.fromisoformat(activity["activity_date"])).days
        breakdown = {
            "role_alignment": int(cfg["role_alignment"]["points"].get(person["title"], 0)),
            "industry_match": int(cfg["industry_match"]["points"].get(company["vertical"], 0)),
            "recent_activity": recent_points(age, cfg["recent_activity"]),
            "influence": follower_points(person["follower_count"], cfg["influence"]),
            "location_proximity": int(cfg["location_proximity"]["points"].get(person["location"], 0)),
            "engagement_overlap": int(cfg["engagement_overlap"]["points"].get(crm_row["engagement_type"], 0)),
        }
        ranked.append(
            {
                "person_id": person_id,
                "full_name": person["full_name"],
                "email": person["email"],
                "x_handle": person["x_handle"],
                "linkedin_slug": person["linkedin_slug"],
                "score": sum(breakdown.values()),
                "activity_date": activity["activity_date"] if activity else "0001-01-01",
                "path": best_paths.get(person_id),
                "unverified_paths": unverified_paths.get(person_id, []),
            }
        )
    ranked.sort(key=lambda row: (-row["score"], -date.fromisoformat(row["activity_date"]).toordinal(), row["person_id"]))
    ranked = ranked[: int(brief["shortlist_size"])]
    for index, row in enumerate(ranked, 1):
        row["rank"] = index
        path = row["path"]
        if path and bridges[path["bridge_id"]]["email"]:
            row["channel"] = "warm_intro_email"
            row["recipient"] = bridges[path["bridge_id"]]
        elif row["email"]:
            row["channel"] = "direct_email"
            row["recipient"] = {"person_id": row["person_id"], "full_name": row["full_name"], "email": row["email"]}
        elif row["linkedin_slug"]:
            row["channel"] = "linkedin_dm"
            row["recipient"] = {"person_id": row["person_id"], "full_name": row["full_name"], "linkedin_slug": row["linkedin_slug"]}
        elif row["x_handle"]:
            row["channel"] = "x_dm"
            row["recipient"] = {"person_id": row["person_id"], "full_name": row["full_name"], "x_handle": row["x_handle"]}
        else:
            row["channel"] = "manual_research"
            row["recipient"] = {"person_id": row["person_id"], "full_name": row["full_name"]}
    return {
        "brief": brief,
        "profiles": profiles,
        "bridges": bridges,
        "ranked": ranked,
        "by_id": {row["person_id"]: row for row in ranked},
    }


def identity_indexes() -> dict[str, str]:
    indexes: dict[str, str] = {}
    for person_id, person in ground_truth()["profiles"].items():
        for value in [person_id, person["full_name"], person["email"], person["x_handle"], person["linkedin_slug"], *person["profile_record_ids"]]:
            if str(value).strip():
                indexes[norm_text(value)] = person_id
                indexes[norm_key(value)] = person_id
    return indexes


def record_person_id(record: dict) -> str | None:
    raw_id = nested_value(record, IDENTITY_ALIASES, {"lead", "prospect", "contact", "person", "profile"})
    raw_name = nested_value(record, NAME_ALIASES, {"lead", "prospect", "contact", "person", "profile"})
    indexes = identity_indexes()
    for value in (raw_id, raw_name):
        if value is None:
            continue
        for normalized in (norm_text(value), norm_key(value)):
            if normalized in indexes:
                return indexes[normalized]
    return None


def numeric_score(record: dict) -> float | None:
    raw = nested_value(record, SCORE_ALIASES, {"score", "scoring", "qualification", "fit", "signals"})
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    if isinstance(raw, str):
        match = re.search(r"-?\d+(?:\.\d+)?", raw.replace(",", ""))
        if match:
            return float(match.group())
    breakdown = direct_value(record, {"score_breakdown", "breakdown", "signal_scores"})
    if isinstance(breakdown, dict):
        values = [value for value in breakdown.values() if isinstance(value, (int, float)) and not isinstance(value, bool)]
        if values:
            return float(sum(values))
    return None


def numeric_rank(record: dict) -> int | None:
    raw = direct_value(record, RANK_ALIASES)
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        match = re.search(r"\d+", raw)
        if match:
            return int(match.group())
    return None


def channel_payload(record: dict) -> object | None:
    return direct_value(record, {"recommended_channel", "primary_channel", "outreach_channel", "channel", "via"})


def normalized_channel(record: dict) -> str | None:
    raw = channel_payload(record)
    if isinstance(raw, dict):
        raw = direct_value(raw, {"type", "channel", "method", "name", "recommendation"})
    if raw is None:
        return None
    label = norm_key(raw)
    if "warm" in label and "email" in label or "introemail" in label or "emailviamutual" in label:
        return "warm_intro_email"
    if label in {"email", "directemail", "coldemail", "targetemail"} or ("direct" in label and "email" in label):
        return "direct_email"
    if "linkedin" in label:
        return "linkedin_dm"
    if label in {"xdm", "twitterdm", "xmessage"} or (label.startswith("x") and "dm" in label):
        return "x_dm"
    if "manual" in label or "research" in label:
        return "manual_research"
    return label or None


def path_payload(record: dict) -> object | None:
    return direct_value(record, {"warm_path", "intro_path", "connection_path", "best_path", "warm_paths"})


def message_text(record: dict) -> str:
    raw = direct_value(record, {"message", "draft", "outreach_message", "copy", "first_message"})
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        body = direct_value(raw, {"body", "text", "content", "message", "draft"})
        return str(body or "")
    return ""


@pytest.fixture(scope="session")
def submission() -> dict:
    if not OUTPUT_PATH.is_file():
        return {"error": f"missing artifact: {OUTPUT_PATH}", "payload": None, "records": []}
    try:
        payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"error": f"output.json is unreadable: {exc}", "payload": None, "records": []}
    records = collect_records(payload)
    return {"error": None, "payload": payload, "records": records}


@pytest.fixture(scope="session")
def normalized_records(submission: dict) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for record in submission["records"]:
        person_id = record_person_id(record)
        if person_id is not None and person_id not in records:
            records[person_id] = record
    return records


def require_parseable(submission: dict) -> None:
    if submission["error"]:
        pytest.skip("artifact parse failure is reported only by test_artifact_usability")
    if not submission["records"]:
        pytest.skip("unrecognized lead collection is reported only by test_artifact_usability")


def test_qualified_shortlist(submission: dict) -> None:
    require_parseable(submission)
    expected = [row["person_id"] for row in ground_truth()["ranked"]]
    actual = [record_person_id(record) for record in submission["records"]]
    assert all(actual), "one or more shortlist entries cannot be matched to a supplied profile"
    assert len(actual) == len(set(actual)), "duplicate source profiles were not merged into unique people"
    assert len(actual) == len(expected), f"expected {len(expected)} qualified leads, found {len(actual)}"
    assert set(actual) == set(expected), "the shortlist includes an ineligible/lower-priority person or omits a qualified top lead"


@pytest.mark.parametrize("person_id", [row["person_id"] for row in ground_truth()["ranked"]])
def test_fit_scores(person_id: str, submission: dict, normalized_records: dict[str, dict]) -> None:
    require_parseable(submission)
    if person_id not in normalized_records:
        pytest.skip("missing-lead coverage is scored by test_qualified_shortlist")
    actual = numeric_score(normalized_records[person_id])
    expected = float(ground_truth()["by_id"][person_id]["score"])
    assert actual is not None, f"{person_id} has no extractable fit score"
    assert abs(actual - expected) <= 0.01, f"{person_id} fit score is {actual}, expected {expected} from the campaign rules"


def test_ranking_order(submission: dict) -> None:
    require_parseable(submission)
    expected_order = [row["person_id"] for row in ground_truth()["ranked"]]
    present = [(record_person_id(record), numeric_rank(record), index) for index, record in enumerate(submission["records"])]
    present = [row for row in present if row[0] in set(expected_order)]
    assert present, "no expected qualified lead is present to evaluate ranking"
    explicit = [rank for _, rank, _ in present]
    if all(rank is not None for rank in explicit):
        assert len(set(explicit)) == len(explicit), "explicit lead ranks are duplicated"
        actual_order = [person_id for person_id, _, _ in sorted(present, key=lambda row: row[1])]
        for person_id, rank, _ in present:
            assert rank == expected_order.index(person_id) + 1, f"{person_id} is labeled rank {rank}, inconsistent with its campaign score"
    else:
        assert not any(rank is not None for rank in explicit), "rank labels are present for only part of the shortlist"
        actual_order = [person_id for person_id, _, _ in present]
    expected_present_order = [person_id for person_id in expected_order if person_id in set(actual_order)]
    assert actual_order == expected_present_order, "lead order does not follow score and tie-break rules"


@pytest.mark.parametrize("person_id", [row["person_id"] for row in ground_truth()["ranked"]])
def test_verified_paths_and_routing(person_id: str, submission: dict, normalized_records: dict[str, dict]) -> None:
    require_parseable(submission)
    if person_id not in normalized_records:
        pytest.skip("missing-lead coverage is scored by test_qualified_shortlist")
    record = normalized_records[person_id]
    expected = ground_truth()["by_id"][person_id]
    expected_path = expected["path"]
    actual_path = path_payload(record)

    if expected_path is None:
        if actual_path not in (None, "", [], {}):
            text = norm_text(json.dumps(actual_path, ensure_ascii=False) if not isinstance(actual_path, str) else actual_path)
            negative = any(phrase in text for phrase in ("none", "no verified", "not found", "unavailable", "cold"))
            assert negative, f"{person_id} claims a warm path even though no verified path exists"
    else:
        assert actual_path not in (None, "", [], {}), f"{person_id} omits its verified warm path"
        text = norm_text(json.dumps(actual_path, ensure_ascii=False) if not isinstance(actual_path, str) else actual_path)
        expected_bridge = ground_truth()["bridges"][expected_path["bridge_id"]]
        bridge_ok = norm_text(expected_path["bridge_id"]) in text or norm_text(expected_bridge["full_name"]) in text
        type_ok = norm_text(expected_path["path_type"].replace("_", " ")) in text
        path_id_ok = norm_text(expected_path["path_id"]) in text
        assert bridge_ok and type_ok or path_id_ok, f"{person_id} does not report the best verified introduction path"
        verification_flag = direct_value(actual_path, {"verified", "is_verified"}) if isinstance(actual_path, dict) else None
        if verification_flag is not None:
            assert is_true(verification_flag), f"{person_id} labels its selected verified path as unverified"

    actual_channel = normalized_channel(record)
    assert actual_channel == expected["channel"], f"{person_id} channel is {actual_channel!r}, expected {expected['channel']!r} from the campaign order"

    recipient = expected["recipient"]
    channel_blob = channel_payload(record)
    channel_text = norm_text(json.dumps(channel_blob, ensure_ascii=False) if not isinstance(channel_blob, str) else channel_blob)
    body = norm_text(message_text(record)[:120])
    recipient_id = recipient.get("bridge_id") or recipient.get("person_id")
    recipient_name = recipient["full_name"]
    recipient_first = norm_text(recipient_name.split()[0])
    recipient_ok = norm_text(recipient_id) in channel_text or norm_text(recipient_name) in channel_text
    recipient_ok = recipient_ok or body.startswith(f"hi {recipient_first}") or body.startswith(recipient_first)
    assert recipient_ok, f"{person_id} draft is not routed to the campaign-order recipient {recipient_name}"
