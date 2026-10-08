from __future__ import annotations

import csv
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

import pytest


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT = RESULTS / "output.json"
SNAPSHOT = date.fromisoformat("2026-06-30")

EXPECTED_DIRECT = {
    "V01": "BeaconForge",
    "V02": "TrailMetric",
    "V03": "QuantaLoop",
    "V04": "FunnelFox",
    "V05": "MetricNest",
}
EXPECTED_TEAM_PRICE = {
    "V01": 699,
    "V02": 549,
    "V03": 399,
    "V04": 299,
    "V05": 249,
}


def norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def walk_scalars(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_scalars(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_scalars(child)
    else:
        yield value


def alias_value(mapping: dict, aliases: set[str], *, recursive: bool = True) -> Any:
    wanted = {norm_key(alias) for alias in aliases}
    for key, value in mapping.items():
        if norm_key(str(key)) in wanted:
            return value
    if recursive:
        for child in mapping.values():
            if isinstance(child, dict):
                found = alias_value(child, aliases, recursive=True)
                if found is not None:
                    return found
    return None


def has_alias_key(value: Any, aliases: set[str]) -> bool:
    wanted = {norm_key(alias) for alias in aliases}
    return any(norm_key(str(key)) in wanted for mapping in walk_dicts(value) for key in mapping)


def load_output() -> dict:
    assert OUTPUT.is_file(), f"missing requested artifact: {OUTPUT}"
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        pytest.fail(f"output.json is not readable UTF-8 JSON: {exc}")
    assert isinstance(payload, dict), "the competitive brief must be represented by a JSON object"
    return payload


DIRECT_LIST_ALIASES = {
    "competitive_set", "direct_competitors", "competitors", "competitor_profiles",
    "competitive set summary", "competitive_set_summary"
}


def extract_competitors(payload: dict) -> list[dict]:
    specific = {norm_key(alias) for alias in DIRECT_LIST_ALIASES if alias != "competitors"}
    generic = norm_key("competitors")
    candidates: list[tuple[int, list[dict]]] = []
    for mapping in walk_dicts(payload):
        for key, value in mapping.items():
            normalized = norm_key(str(key))
            if normalized in specific | {generic} and isinstance(value, list):
                rows = [row for row in value if isinstance(row, dict)]
                if rows:
                    if normalized == generic:
                        marked_direct = []
                        for row in rows:
                            label = alias_value(row, {"classification", "competitor_type", "directness", "relationship"})
                            if label is not None and "direct" in norm_key(str(label)) and "indirect" not in norm_key(str(label)):
                                marked_direct.append(row)
                        rows = marked_direct or rows
                    candidates.append((1 if normalized in specific else 0, rows))
    if not candidates:
        return []
    return max(candidates, key=lambda item: (item[0], len(item[1])))[1]


def identity(row: dict) -> str | None:
    value = alias_value(row, {"vendor_id", "competitor_id", "id", "name", "company", "vendor"})
    if value is None:
        return None
    raw = norm_key(str(value))
    for vendor_id, name in EXPECTED_DIRECT.items():
        if raw in {norm_key(vendor_id), norm_key(name)}:
            return vendor_id
    return str(value).strip()


def by_identity(payload: dict) -> dict[str, dict]:
    found = {}
    for row in extract_competitors(payload):
        key = identity(row)
        if key:
            found[key] = row
    return found


def top_section(payload: dict, aliases: set[str]) -> Any:
    wanted = {norm_key(alias) for alias in aliases}
    for key, value in payload.items():
        if norm_key(str(key)) in wanted:
            return value
    for mapping in walk_dicts(payload):
        for key, value in mapping.items():
            if norm_key(str(key)) in wanted:
                return value
    return None


def pricing_blob(row: dict) -> str:
    section = alias_value(row, {"pricing", "price", "commercials", "business_model", "business model and pricing", "plans"})
    if section is None:
        return ""
    return json.dumps(section, ensure_ascii=False, sort_keys=True).casefold()


def contains_number(blob: str, expected: int) -> bool:
    return re.search(rf"(?<!\d){expected}(?:\.0+)?(?!\d)", blob.replace(",", "")) is not None


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (DATA / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def evidence_catalog() -> tuple[set[str], set[str], dict[str, str]]:
    all_ids: set[str] = set()
    in_scope: set[str] = set()
    vendor_for: dict[str, str] = {}

    product = json.loads((DATA / "product_brief.json").read_text(encoding="utf-8"))
    for mapping in walk_dicts(product):
        for key, value in mapping.items():
            if "evidence" in norm_key(str(key)) and isinstance(value, str):
                all_ids.add(value)
                in_scope.add(value)

    for name in ("vendors.csv", "features.csv", "pricing.csv"):
        for row in read_csv(name):
            evidence_id = row.get("evidence_id", "")
            if not evidence_id:
                continue
            all_ids.add(evidence_id)
            vendor_for[evidence_id] = row.get("vendor_id", "")
            valid = True
            if name == "features.csv":
                valid = date.fromisoformat(row["observed_at"]) <= SNAPSHOT
            elif name == "pricing.csv":
                valid = (
                    row["status"] == "active"
                    and date.fromisoformat(row["effective_from"]) <= SNAPSHOT
                    and (not row["effective_to"] or date.fromisoformat(row["effective_to"]) >= SNAPSHOT)
                )
            if valid:
                in_scope.add(evidence_id)

    for name in ("customer_feedback.jsonl", "market_moves.jsonl"):
        for row in read_jsonl(name):
            evidence_id = row["evidence_id"]
            all_ids.add(evidence_id)
            vendor_for[evidence_id] = row["vendor_id"]
            if name == "customer_feedback.jsonl":
                valid = date.fromisoformat(row["observed_at"]) <= SNAPSHOT
            else:
                valid = date.fromisoformat(row["event_date"]) <= SNAPSHOT and row["status"] == "completed"
            if valid:
                in_scope.add(evidence_id)
    return all_ids, in_scope, vendor_for


EVIDENCE_RE = re.compile(r"\b(?:PB|VF|PX|FS|FB|MV)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", re.IGNORECASE)


def cited_ids(payload: dict) -> set[str]:
    found = set()
    for scalar in walk_scalars(payload):
        if isinstance(scalar, str):
            found.update(match.upper() for match in EVIDENCE_RE.findall(scalar))
    return found


def test_artifact_usability_and_requested_scope():
    payload = load_output()
    competitors = extract_competitors(payload)
    assert competitors, "the brief has no recognizable direct-competitor profiles"
    required_profile_parts = {
        "position": {"market_position", "market_positioning", "position", "position_summary", "tier", "market_role"},
        "strengths": {"strengths", "advantages", "core_product_strengths"},
        "weaknesses": {"weaknesses", "gaps", "limitations", "product_weaknesses", "product_weaknesses_and_gaps"},
        "pricing": {"pricing", "price", "commercials", "business_model", "business model and pricing", "plans"},
        "threat": {"threat", "threats", "threats_to_nimblesignal", "competitive_risk", "competitive_threats", "competitive threats and advantages"},
    }
    for row in competitors:
        missing = [label for label, aliases in required_profile_parts.items() if not has_alias_key(row, aliases)]
        assert not missing, f"competitor {identity(row) or '<unnamed>'} is missing requested parts: {missing}"
    opportunities = top_section(payload, {"differentiation_opportunities", "differentiation", "opportunities", "white_space", "differentiators"})
    recommendation = top_section(payload, {"positioning_recommendation", "competitive_positioning", "recommendation", "recommendations", "strategy", "positioning_stance"})
    assert opportunities, "the brief has no recognizable differentiation opportunities"
    assert recommendation, "the brief has no recognizable positioning recommendation"


def test_direct_competitor_set():
    payload = load_output()
    actual = set(by_identity(payload))
    expected = set(EXPECTED_DIRECT)
    assert actual == expected, (
        f"direct set mismatch: missing {sorted(expected - actual)}, unexpected {sorted(actual - expected)}; "
        "misclassifying adjacent tools distorts the launch landscape"
    )


@pytest.mark.parametrize("vendor_id", sorted(EXPECTED_DIRECT))
def test_current_pricing_accuracy(vendor_id: str):
    payload = load_output()
    competitors = by_identity(payload)
    if vendor_id not in competitors:
        pytest.skip("direct-set coverage is scored by its own criterion")
    blob = pricing_blob(competitors[vendor_id])
    assert blob, f"{EXPECTED_DIRECT[vendor_id]} has no readable pricing section"
    expected = EXPECTED_TEAM_PRICE[vendor_id]
    assert contains_number(blob, expected), (
        f"{EXPECTED_DIRECT[vendor_id]} pricing does not show the snapshot-date Team price of ${expected}; "
        "a stale or future price would mislead launch planning"
    )
    assert any(term in blob for term in ("month", "monthly", "annual", "contract", "workspace", "platform")), (
        f"{EXPECTED_DIRECT[vendor_id]} gives a number without enough billing context to interpret it"
    )


def test_evidence_traceability_and_snapshot_integrity():
    payload = load_output()
    all_ids, in_scope_ids, _vendor_for = evidence_catalog()
    citations = cited_ids(payload)
    unknown = citations - all_ids
    out_of_scope = citations - in_scope_ids
    assert not unknown, f"citations do not resolve to the local packet: {sorted(unknown)}"
    assert not out_of_scope, (
        f"citations rely on evidence not in force by 2026-06-30: {sorted(out_of_scope)}"
    )
    assert len(citations) >= 11, "too few distinct local records are cited to trace the brief's material claims"
    assert {"PB-001", "PB-002"} & citations, "the recommendations never cite the supplied NimbleSignal brief"
    metricnest = by_identity(payload).get("V05")
    if metricnest is not None:
        founded = alias_value(metricnest, {"founded_year", "founding_year", "founded"})
        if founded is not None:
            assert norm_key(str(founded)) in {"", "unknown", "notavailable", "na", "null", "none"}, (
                "MetricNest's founding year is absent from the packet and must not be fabricated"
            )
