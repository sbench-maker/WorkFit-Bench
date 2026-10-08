from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import re
from typing import Any

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
OUTPUT_FILE = Path(os.environ.get("TASK_OUTPUT_FILE", "/root/results/output.json"))


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _first(mapping: object, names: tuple[str, ...]) -> object | None:
    if not isinstance(mapping, dict):
        return None
    wanted = {_norm(name) for name in names}
    for key, value in mapping.items():
        if _norm(key) in wanted:
            return value
    for container_name in ("audit", "security", "analysis", "result", "details", "risk"):
        nested = next(
            (value for key, value in mapping.items() if _norm(key) == container_name),
            None,
        )
        if isinstance(nested, dict):
            for key, value in nested.items():
                if _norm(key) in wanted:
                    return value
    return None


def _output() -> dict:
    payload = _load_json(OUTPUT_FILE)
    assert isinstance(payload, dict), "output.json must contain one JSON object"
    return payload


def _rows(payload: dict) -> list[dict]:
    raw: object | None = None
    for key, value in payload.items():
        if _norm(key) in {
            "reviews",
            "results",
            "items",
            "records",
            "tokens",
            "audits",
            "security_reviews",
        }:
            raw = value
            break
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if isinstance(raw, dict):
        rows = []
        for key, value in raw.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("review_id", key)
                rows.append(row)
        return rows
    return []


def _row_id(row: dict) -> str:
    value = _first(row, ("review_id", "queue_id", "swap_id", "id"))
    return str(value).strip() if value is not None else ""


def _row_map(payload: dict) -> tuple[dict[str, dict], list[str]]:
    mapped: dict[str, dict] = {}
    duplicates: list[str] = []
    for row in _rows(payload):
        identity = _row_id(row)
        if not identity:
            continue
        if identity in mapped:
            duplicates.append(identity)
        mapped[identity] = row
    return mapped, duplicates


def _as_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    normalized = _norm(value)
    if normalized in {"true", "yes", "1", "available", "usable", "supported"}:
        return True
    if normalized in {"false", "no", "0", "unavailable", "unsupported", "not_available"}:
        return False
    return None


def _as_number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "")
    if not text or _norm(text) in {"none", "null", "unknown", "n_a", "na"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _canonical_disposition(value: object) -> str | None:
    normalized = _norm(value)
    aliases = {
        "DATA_UNAVAILABLE": {
            "data_unavailable",
            "unavailable",
            "audit_unavailable",
            "no_result",
            "unsupported",
            "verify_and_retry",
            "retry_later",
        },
        "BLOCK": {"block", "blocked", "reject", "do_not_trade", "do_not_proceed"},
        "AVOID": {"avoid", "avoid_trading", "high_risk_avoid"},
        "REVIEW": {"review", "manual_review", "exercise_caution", "caution", "hold_for_review"},
        "PROCEED_WITH_CAUTION": {
            "proceed_with_caution",
            "proceed_cautiously",
            "lower_risk_proceed",
            "proceed",
        },
    }
    for canonical, values in aliases.items():
        if normalized in values:
            return canonical
    return None


def _availability(row: dict) -> bool | None:
    value = _first(
        row,
        ("audit_available", "audit_usable", "available", "usable", "has_audit"),
    )
    parsed = _as_bool(value)
    if parsed is not None:
        return parsed
    disposition = _canonical_disposition(
        _first(row, ("disposition", "action", "decision", "recommendation", "status"))
    )
    if disposition == "DATA_UNAVAILABLE":
        return False
    if disposition in {"BLOCK", "AVOID", "REVIEW", "PROCEED_WITH_CAUTION"}:
        return True
    return None


def _risk_level(row: dict) -> int | None:
    value = _first(row, ("risk_level", "riskLevel", "level", "risk_score"))
    if isinstance(value, dict):
        value = _first(value, ("level", "score", "value", "numeric"))
    number = _as_number(value)
    if number is None or not number.is_integer():
        return None
    return int(number)


def _risk_label(row: dict) -> str | None:
    value = _first(row, ("risk_level_label", "riskLevelEnum", "risk_label", "severity"))
    if value is None:
        value = _first(_first(row, ("risk_level", "riskLevel")), ("label", "name", "severity"))
    if value is None or not str(value).strip():
        return None
    normalized = _norm(value).upper()
    return normalized if normalized in {"LOW", "MEDIUM", "HIGH"} else None


def _tax_parts(row: dict, side: str) -> tuple[bool, float | None, str | None]:
    side_norm = _norm(side)
    container = _first(row, ("taxes", "tax_assessment", "tax_info", "tax", "extra_info", "extraInfo"))
    raw: object | None = None
    assessment_from_container: object | None = None
    if isinstance(container, dict):
        raw = next(
            (value for key, value in container.items() if _norm(key) in {side_norm, f"{side_norm}_tax"}),
            None,
        )
        assessment_from_container = _first(
            container, (f"{side}_tax_assessment", f"{side}_assessment", f"{side}TaxAssessment")
        )
    if raw is None:
        raw = _first(row, (f"{side}_tax", f"{side}Tax", f"{side}_tax_percent"))

    present = raw is not None
    if isinstance(raw, dict):
        percent_raw = _first(raw, ("percent", "percentage", "value", "tax", "rate"))
        assessment_raw = _first(raw, ("assessment", "band", "status", "classification"))
        present = True
    else:
        percent_raw = raw
        assessment_raw = assessment_from_container or _first(
            row,
            (f"{side}_tax_assessment", f"{side}_assessment", f"{side}TaxAssessment"),
        )
    assessment = None
    if isinstance(raw, str) and assessment_raw is None:
        combined = _norm(raw)
        for candidate in ("acceptable", "warning", "critical", "unknown"):
            if candidate in combined:
                assessment_raw = candidate
                break
        match = re.search(r"[-+]?\d+(?:\.\d+)?", raw)
        if match:
            percent_raw = match.group(0)
    if assessment_raw is not None:
        value = _norm(assessment_raw).upper()
        assessment_aliases = {
            "OK": "ACCEPTABLE",
            "NORMAL": "ACCEPTABLE",
            "ACCEPTABLE": "ACCEPTABLE",
            "WARNING": "WARNING",
            "WARN": "WARNING",
            "CRITICAL": "CRITICAL",
            "HIGH": "CRITICAL",
            "UNKNOWN": "UNKNOWN",
            "N_A": "UNKNOWN",
            "NA": "UNKNOWN",
        }
        assessment = assessment_aliases.get(value)
    return present, _as_number(percent_raw), assessment


def _flatten_flags(raw: object, inherited_category: str | None = None) -> list[dict]:
    found: list[dict] = []
    if isinstance(raw, list):
        for item in raw:
            found.extend(_flatten_flags(item, inherited_category))
        return found
    if not isinstance(raw, dict):
        return found

    category_value = _first(raw, ("category", "category_id", "id", "risk_category"))
    category = str(category_value).strip() if category_value is not None else inherited_category
    details = _first(raw, ("details", "findings", "risks", "flags", "items"))
    if isinstance(details, (list, dict)):
        found.extend(_flatten_flags(details, category))
        return found

    hit = _first(raw, ("isHit", "is_hit", "detected", "hit", "triggered"))
    if _as_bool(hit) is False:
        return found
    title = _first(raw, ("title", "name", "flag", "finding"))
    description = _first(raw, ("description", "evidence", "detail", "reason"))
    if title is not None:
        found.append(
            {
                "category": category,
                "title": str(title).strip(),
                "description": "" if description is None else str(description).strip(),
            }
        )
        return found
    for key, value in raw.items():
        if isinstance(value, (list, dict)):
            found.extend(_flatten_flags(value, str(key)))
    return found


def _flags(row: dict) -> list[dict]:
    raw = _first(
        row,
        ("detected_risks", "risk_flags", "risks", "findings", "detected_flags"),
    )
    return _flatten_flags(raw)


def _canonical_category(value: object) -> str:
    normalized = _norm(value)
    aliases = {
        "contract": "CONTRACT_RISK",
        "contract_risk": "CONTRACT_RISK",
        "trade": "TRADE_RISK",
        "trading": "TRADE_RISK",
        "trade_risk": "TRADE_RISK",
        "trading_risk": "TRADE_RISK",
        "scam": "SCAM_RISK",
        "scam_risk": "SCAM_RISK",
    }
    return aliases.get(normalized, normalized.upper())


def _expected() -> dict[str, dict]:
    queue = _load_json(DATA_DIR / "review_queue.json")
    audits = _load_json(DATA_DIR / "audit_responses.json")
    assert isinstance(queue, list) and isinstance(audits, list)
    by_request = {row["audit_request_id"]: row for row in audits}
    expected = {}
    for request in queue:
        data = by_request[request["audit_request_id"]]["response"]["data"]
        usable = data.get("hasResult") is True and data.get("isSupported") is True
        row: dict[str, Any] = {
            "request": request,
            "usable": usable,
            "risk_level": None,
            "risk_label": None,
            "buy": (None, None),
            "sell": (None, None),
            "flags": set(),
            "disposition": "DATA_UNAVAILABLE",
        }
        if usable:
            level = int(data["riskLevel"])
            extra = data.get("extraInfo") or {}

            def band(value: object) -> str:
                if value is None:
                    return "UNKNOWN"
                number = float(value)
                return "ACCEPTABLE" if number < 5 else "WARNING" if number <= 10 else "CRITICAL"

            buy_band = band(extra.get("buyTax"))
            sell_band = band(extra.get("sellTax"))
            flags = set()
            for group in data.get("riskItems", []):
                for detail in group.get("details", []):
                    if detail.get("isHit") is True:
                        flags.add((group.get("id"), detail.get("title"), detail.get("description")))
            if level == 5:
                decision = "BLOCK"
            elif level == 4 or "CRITICAL" in (buy_band, sell_band):
                decision = "AVOID"
            elif level in (2, 3) or "WARNING" in (buy_band, sell_band) or flags:
                decision = "REVIEW"
            else:
                decision = "PROCEED_WITH_CAUTION"
            row.update(
                {
                    "risk_level": level,
                    "risk_label": data["riskLevelEnum"],
                    "buy": (None if extra.get("buyTax") is None else float(extra["buyTax"]), buy_band),
                    "sell": (None if extra.get("sellTax") is None else float(extra["sellTax"]), sell_band),
                    "flags": flags,
                    "disposition": decision,
                }
            )
        expected[request["review_id"]] = row
    return expected


EXPECTED = _expected()
DECISION_CLASSES = ("BLOCK", "AVOID", "REVIEW", "PROCEED_WITH_CAUTION")
TAX_BANDS = ("ACCEPTABLE", "WARNING", "CRITICAL", "UNKNOWN")


def test_request_scope_and_identity() -> None:
    payload = _output()
    rows, duplicates = _row_map(payload)
    issues = []
    if duplicates:
        issues.append(f"duplicate review IDs: {sorted(set(duplicates))[:10]}")
    missing = sorted(set(EXPECTED) - set(rows))
    extra = sorted(set(rows) - set(EXPECTED))
    if missing or extra:
        issues.append(f"scope mismatch: missing={missing[:10]}, extra={extra[:10]}")
    for review_id, expected in EXPECTED.items():
        row = rows.get(review_id)
        if row is None:
            continue
        request = expected["request"]
        chain = _first(row, ("chain_id", "chainId", "binanceChainId", "chain"))
        address = _first(row, ("contract_address", "contractAddress", "address", "token_address"))
        audit_id = _first(row, ("audit_request_id", "auditRequestId", "request_uuid"))
        if chain is None or str(chain).strip() != request["binanceChainId"]:
            issues.append(f"{review_id} does not preserve its chain identifier")
        if address is None or str(address).strip().lower() != request["contractAddress"].lower():
            issues.append(f"{review_id} does not preserve its contract address")
        if audit_id is not None and str(audit_id).strip() != request["audit_request_id"]:
            issues.append(f"{review_id} is linked to the wrong audit request")
        if len(issues) >= 25:
            break
    assert not issues, "queue coverage or identity errors:\n- " + "\n- ".join(issues)


def test_audit_validity_handling() -> None:
    rows, _ = _row_map(_output())
    issues = []
    for review_id, expected in EXPECTED.items():
        row = rows.get(review_id)
        if row is None:
            continue
        actual_available = _availability(row)
        if actual_available is not expected["usable"]:
            issues.append(
                f"{review_id} availability is {actual_available!r}, expected {expected['usable']!r}"
            )
            continue
        if not expected["usable"]:
            decision = _canonical_disposition(
                _first(row, ("disposition", "action", "decision", "recommendation", "status"))
            )
            buy_present, buy_value, buy_band = _tax_parts(row, "buy")
            sell_present, sell_value, sell_band = _tax_parts(row, "sell")
            material_tax = (
                (buy_present and (buy_value is not None or buy_band not in (None, "UNKNOWN")))
                or (sell_present and (sell_value is not None or sell_band not in (None, "UNKNOWN")))
            )
            if decision != "DATA_UNAVAILABLE":
                issues.append(f"{review_id} must be marked data-unavailable")
            if _risk_level(row) is not None or _risk_label(row) is not None:
                issues.append(f"{review_id} surfaces an unreliable risk level")
            if material_tax or _flags(row):
                issues.append(f"{review_id} surfaces unreliable tax or risk-item details")
        if len(issues) >= 25:
            break
    assert not issues, "audit validity errors:\n- " + "\n- ".join(issues)


@pytest.mark.parametrize("expected_decision", DECISION_CLASSES)
def test_risk_levels_and_dispositions(expected_decision: str) -> None:
    rows, _ = _row_map(_output())
    selected = [
        (review_id, expected)
        for review_id, expected in EXPECTED.items()
        if expected["usable"] and expected["disposition"] == expected_decision
    ]
    assert selected, f"authoring error: no expected rows for {expected_decision}"
    issues = []
    for review_id, expected in selected:
        row = rows.get(review_id)
        if row is None:
            continue
        decision = _canonical_disposition(
            _first(row, ("disposition", "action", "decision", "recommendation", "status"))
        )
        if decision != expected_decision:
            issues.append(
                f"{review_id} disposition is {decision!r}, expected {expected_decision!r}"
            )
        level = _risk_level(row)
        label = _risk_label(row)
        if level is None and label is None:
            issues.append(f"{review_id} omits its usable risk level")
        if level is not None and level != expected["risk_level"]:
            issues.append(f"{review_id} has numeric risk level {level}, expected {expected['risk_level']}")
        if label is not None and label != expected["risk_label"]:
            issues.append(f"{review_id} has risk label {label!r}, expected {expected['risk_label']!r}")
        if len(issues) >= 25:
            break
    assert not issues, (
        f"{expected_decision} risk-level or disposition errors; the desk could take the wrong pre-trade action:\n- "
        + "\n- ".join(issues)
    )


@pytest.mark.parametrize("expected_band", TAX_BANDS)
def test_tax_assessments_and_values(expected_band: str) -> None:
    rows, _ = _row_map(_output())
    selected = [
        (review_id, side, expected_value)
        for review_id, expected in EXPECTED.items()
        if expected["usable"]
        for side in ("buy", "sell")
        for expected_value, band in (expected[side],)
        if band == expected_band
    ]
    assert selected, f"authoring error: no expected tax values in {expected_band}"
    issues = []
    for review_id, side, expected_value in selected:
        row = rows.get(review_id)
        if row is None:
            continue
        present, value, assessment = _tax_parts(row, side)
        if not present:
            issues.append(f"{review_id} omits the {side}-tax result")
            continue
        if expected_value is None:
            if value is not None:
                issues.append(f"{review_id} invents numeric {side} tax {value!r} for an unknown value")
        elif value is None or abs(value - expected_value) >= 1e-9:
            issues.append(f"{review_id} {side} tax is {value!r}, expected {expected_value}")
        if assessment != expected_band:
            issues.append(
                f"{review_id} {side}-tax assessment is {assessment!r}, expected {expected_band!r}"
            )
        if len(issues) >= 25:
            break
    assert not issues, f"{expected_band} tax errors:\n- " + "\n- ".join(issues)


def test_all_detected_risk_flags() -> None:
    rows, _ = _row_map(_output())
    issues = []
    for review_id, expected in EXPECTED.items():
        row = rows.get(review_id)
        if row is None or not expected["usable"]:
            continue
        actual = {
            (
                _canonical_category(flag.get("category")),
                flag.get("title"),
                flag.get("description"),
            )
            for flag in _flags(row)
        }
        if actual != expected["flags"]:
            missing = expected["flags"] - actual
            extra = actual - expected["flags"]
            issues.append(
                f"{review_id} risk flags differ: missing={sorted(missing)!r}, extra={sorted(extra)!r}"
            )
        if len(issues) >= 15:
            break
    assert not issues, "detected-risk coverage errors:\n- " + "\n- ".join(issues)


def _summary(payload: dict) -> dict:
    value = _first(payload, ("summary", "queue_summary", "triage_summary", "overview"))
    return value if isinstance(value, dict) else {}


def _summary_number(summary: dict, names: tuple[str, ...]) -> int | None:
    number = _as_number(_first(summary, names))
    return int(number) if number is not None and number.is_integer() else None


def _count_mapping(raw: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    if isinstance(raw, dict):
        iterable = raw.items()
    elif isinstance(raw, list):
        iterable = []
        for row in raw:
            if isinstance(row, dict):
                label = _first(row, ("disposition", "status", "decision", "name", "label"))
                count = _first(row, ("count", "total", "value"))
                iterable.append((label, count))
    else:
        iterable = []
    for label, value in iterable:
        canonical = _canonical_disposition(label)
        if isinstance(value, dict):
            value = _first(value, ("count", "total", "value"))
        number = _as_number(value)
        if canonical is not None and number is not None and number.is_integer():
            counts[canonical] = int(number)
    return counts


def test_summary_reconciliation() -> None:
    payload = _output()
    summary = _summary(payload)
    rows, _ = _row_map(payload)
    detailed_counts = Counter()
    detailed_usable = 0
    detailed_unavailable = 0
    unclassified = []
    for review_id, row in rows.items():
        decision = _canonical_disposition(
            _first(row, ("disposition", "action", "decision", "recommendation", "status"))
        )
        available = _availability(row)
        if decision is None:
            unclassified.append(review_id)
        else:
            detailed_counts[decision] += 1
        if available is True:
            detailed_usable += 1
        elif available is False:
            detailed_unavailable += 1
    total = _summary_number(summary, ("total_requests", "total_reviewed", "total", "queue_total", "request_count"))
    usable = _summary_number(summary, ("usable_audits", "available_audits", "usable", "assessed"))
    unavailable = _summary_number(
        summary,
        ("unavailable_audits", "data_unavailable", "unavailable", "not_assessed"),
    )
    disposition_raw = _first(
        summary,
        ("by_disposition", "disposition_breakdown", "disposition_counts", "decisions", "actions", "by_action"),
    )
    actual_counts = _count_mapping(disposition_raw)
    if unavailable is None and "DATA_UNAVAILABLE" in actual_counts:
        unavailable = actual_counts["DATA_UNAVAILABLE"]
    if usable is None and total is not None and unavailable is not None:
        usable = total - unavailable
    issues = []
    if unclassified:
        issues.append(f"detailed rows have unrecognized dispositions: {unclassified[:10]}")
    if total != len(rows):
        issues.append(f"summary total is {total!r}, but the detail contains {len(rows)} rows")
    if usable != detailed_usable:
        issues.append(f"summary usable count is {usable!r}, but the detail contains {detailed_usable}")
    if unavailable != detailed_unavailable:
        issues.append(
            f"summary unavailable count is {unavailable!r}, but the detail contains {detailed_unavailable}"
        )
    if actual_counts != dict(detailed_counts):
        issues.append(
            f"summary disposition counts are {actual_counts!r}, but the detail contains {dict(detailed_counts)!r}"
        )
    assert not issues, "queue summary does not reconcile:\n- " + "\n- ".join(issues)
