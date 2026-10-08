from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import math
import os
from pathlib import Path
import re
import subprocess

import pytest


DATA_ROOT = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_ROOT = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
VERIFIER_ROOT = Path(os.environ.get("TASK_VERIFIER_DIR", "/verifier"))
CODE_PATH = RESULTS_ROOT / "code.js"
INPUT_PATH = DATA_ROOT / "webhook_items.json"
RUNNER = VERIFIER_ROOT / "run_code_node.js"
SUPPORTED = ("USD", "EUR", "GBP")


def _is_object(value) -> bool:
    return isinstance(value, dict)


def _clean_id(value):
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _timestamp(value):
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not re.search(r"(?:Z|[+-]\d{2}:\d{2})$", cleaned, re.I):
        return None
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    utc = parsed.astimezone(timezone.utc)
    return parsed.timestamp(), utc.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _money_cents(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        decimal = Decimal(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            return None
        decimal = Decimal(str(value))
    elif isinstance(value, str):
        cleaned = value.strip()
        if not re.fullmatch(r"\d+(?:\.\d{1,2})?", cleaned):
            return None
        try:
            decimal = Decimal(cleaned)
        except InvalidOperation:
            return None
    else:
        return None
    if decimal < 0 or decimal.as_tuple().exponent < -2:
        return None
    cents = decimal * 100
    if cents != cents.to_integral_value():
        return None
    result = int(cents)
    return result if abs(result) <= 9_007_199_254_740_991 else None


def _expected(items: list) -> dict:
    invalid = []
    valid = []
    for input_index, item in enumerate(items):
        json_data = item.get("json") if _is_object(item) and _is_object(item.get("json")) else None
        body = json_data.get("body") if json_data and _is_object(json_data.get("body")) else None
        received = _timestamp(json_data.get("received_at")) if json_data else None
        reasons = []
        if not json_data or not body or not received:
            reasons.append("INVALID_ENVELOPE")

        event_id = _clean_id(body.get("event_id")) if body else None
        order_id = _clean_id(body.get("order_id")) if body else None
        customer = body.get("customer") if body and _is_object(body.get("customer")) else None
        customer_id = _clean_id(customer.get("id")) if customer else None
        if body and not event_id:
            reasons.append("MISSING_EVENT_ID")
        if body and not order_id:
            reasons.append("MISSING_ORDER_ID")
        if body and not customer_id:
            reasons.append("MISSING_CUSTOMER_ID")

        event_type = body.get("event_type").strip().lower() if body and isinstance(body.get("event_type"), str) else None
        if body and event_type not in {"paid", "refunded", "cancelled"}:
            reasons.append("UNSUPPORTED_EVENT_TYPE")
        occurred = _timestamp(body.get("occurred_at")) if body else None
        if body and not occurred:
            reasons.append("INVALID_TIMESTAMP")
        currency = body.get("currency").strip().upper() if body and isinstance(body.get("currency"), str) else None
        if body and currency not in SUPPORTED:
            reasons.append("UNSUPPORTED_CURRENCY")

        total_cents = None
        if body:
            amounts = body.get("amounts") if _is_object(body.get("amounts")) else None
            values = [_money_cents(amounts.get(key)) for key in ("subtotal", "tax", "shipping", "discount")] if amounts else []
            if len(values) == 4 and all(value is not None for value in values):
                candidate = values[0] + values[1] + values[2] - values[3]
                if candidate > 0:
                    total_cents = candidate
            if total_cents is None:
                reasons.append("INVALID_AMOUNT")

        if reasons:
            invalid.append({
                "eventId": event_id,
                "orderId": order_id,
                "inputIndex": input_index,
                "reasons": frozenset(reasons),
            })
        else:
            valid.append({
                "inputIndex": input_index,
                "eventId": event_id,
                "orderId": order_id,
                "customerId": customer_id,
                "eventType": event_type,
                "occurredAtUtc": occurred[1],
                "currency": currency,
                "amountCents": total_cents,
                "received": received[0],
            })

    selected = {}
    for row in valid:
        previous = selected.get(row["eventId"])
        if previous is None or (row["received"], row["inputIndex"]) > (previous["received"], previous["inputIndex"]):
            selected[row["eventId"]] = row

    ledgers = {}
    quarantines = list(invalid)
    totals = {currency: 0 for currency in SUPPORTED}
    for row in selected.values():
        if row["eventType"] == "cancelled":
            quarantines.append({
                "eventId": row["eventId"],
                "orderId": row["orderId"],
                "inputIndex": row["inputIndex"],
                "reasons": frozenset({"CANCELLED"}),
            })
            continue
        signed = -row["amountCents"] if row["eventType"] == "refunded" else row["amountCents"]
        ledger = {
            "eventId": row["eventId"],
            "orderId": row["orderId"],
            "eventType": row["eventType"],
            "occurredAtUtc": row["occurredAtUtc"],
            "currency": row["currency"],
            "signedAmountCents": signed,
            "customerId": row["customerId"],
            "inputIndex": row["inputIndex"],
        }
        ledgers[row["eventId"]] = ledger
        totals[row["currency"]] += signed

    summary = {
        "inputCount": len(items),
        "canonicalEventCount": len(selected),
        "duplicateRetries": len(valid) - len(selected),
        "ledgerCount": len(ledgers),
        "quarantineCount": len(quarantines),
        "netByCurrencyCents": totals,
    }
    return {"ledgers": ledgers, "quarantines": quarantines, "summary": summary}


def _run(items: list, tmp_path: Path) -> list[dict]:
    assert CODE_PATH.is_file(), f"the requested {CODE_PATH} is missing"
    input_file = tmp_path / "input.json"
    input_file.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    completed = subprocess.run(
        ["node", str(RUNNER), str(CODE_PATH), str(input_file)],
        text=True,
        capture_output=True,
        timeout=8,
        check=False,
    )
    assert completed.returncode == 0, f"Code node execution failed: {completed.stderr.strip()}"
    try:
        output = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Code node runner returned unreadable JSON: {exc}")
    assert isinstance(output, list), "Code node output did not normalize to an item array"
    assert all(_is_object(item) and _is_object(item.get("json")) for item in output), (
        "every returned n8n item must contain an object-valued json field"
    )
    return output


def _partition(output: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    ledger = [item for item in output if item["json"].get("recordType") == "ledger"]
    quarantine = [item for item in output if item["json"].get("recordType") == "quarantine"]
    summary = [item for item in output if item["json"].get("recordType") == "summary"]
    unknown = [item for item in output if item["json"].get("recordType") not in {"ledger", "quarantine", "summary"}]
    assert not unknown, f"output contains {len(unknown)} items with an unknown recordType"
    return ledger, quarantine, summary


def _primary_items() -> list:
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    return payload


def test_artifact_is_paste_ready_and_executable(tmp_path):
    assert CODE_PATH.is_file(), f"the requested {CODE_PATH} is missing"
    try:
        code = CODE_PATH.read_text(encoding="utf-8")
    except UnicodeError as exc:
        pytest.fail(f"code.js is not readable UTF-8: {exc}")
    assert code.strip(), "code.js is empty"
    output = _run(_primary_items(), tmp_path)
    ledger, quarantine, summary = _partition(output)
    assert ledger and quarantine, "the node does not emit both ledger and quarantine details for the supplied batch"
    assert len(summary) == 1, "the node must emit exactly one aggregate summary"


def test_selected_events_are_normalized_and_deduplicated(tmp_path):
    items = _primary_items()
    expected = _expected(items)["ledgers"]
    output = _run(items, tmp_path)
    actual_items, _, _ = _partition(output)
    actual = {}
    for item in actual_items:
        row = item["json"]
        event_id = row.get("eventId")
        assert event_id not in actual, f"ledger event {event_id!r} was emitted more than once"
        actual[event_id] = row
    assert set(actual) == set(expected), "ledger output does not cover exactly the selected paid/refunded event IDs"
    fields = ("eventId", "orderId", "eventType", "occurredAtUtc", "currency", "signedAmountCents", "customerId")
    mismatches = []
    for event_id, wanted in expected.items():
        got = actual[event_id]
        wrong = {field: (got.get(field), wanted[field]) for field in fields if got.get(field) != wanted[field]}
        if wrong:
            mismatches.append((event_id, wrong))
    assert not mismatches, f"normalized ledger values are wrong for {len(mismatches)} events; examples: {mismatches[:4]}"


@pytest.mark.parametrize("case_name", ["fixture", "empty"])
def test_quarantine_scope_and_batch_resilience(tmp_path, case_name):
    items = _primary_items() if case_name == "fixture" else []
    expected = _expected(items)["quarantines"]
    output = _run(items, tmp_path)
    _, actual_items, summaries = _partition(output)
    if case_name == "empty":
        assert actual_items == [] and len(summaries) == 1, "empty input must return only the zero-valued summary"
        return
    actual_counter = Counter()
    for item in actual_items:
        row = item["json"]
        reasons = row.get("reasons")
        assert isinstance(reasons, list) and reasons, "each quarantine detail needs one or more reason codes"
        actual_counter[(row.get("inputIndex"), row.get("eventId"), row.get("orderId"), frozenset(reasons))] += 1
    expected_counter = Counter(
        (row["inputIndex"], row["eventId"], row["orderId"], row["reasons"]) for row in expected
    )
    assert actual_counter == expected_counter, "invalid deliveries or selected cancellations are missing, duplicated, or misclassified"


@pytest.mark.parametrize("case_name", ["fixture", "empty"])
def test_summary_reconciles_exactly(tmp_path, case_name):
    items = _primary_items() if case_name == "fixture" else []
    expected = _expected(items)["summary"]
    output = _run(items, tmp_path)
    _, _, summaries = _partition(output)
    assert len(summaries) == 1, "exactly one summary item is required"
    actual = summaries[0]["json"]
    mismatches = {field: (actual.get(field), value) for field, value in expected.items() if actual.get(field) != value}
    assert not mismatches, f"summary counts or currency totals do not reconcile: {mismatches}"


def test_detail_items_preserve_source_linkage(tmp_path):
    items = _primary_items()
    output = _run(items, tmp_path)
    ledger, quarantine, _ = _partition(output)
    expected = _expected(items)
    ledger_index = {event_id: row["inputIndex"] for event_id, row in expected["ledgers"].items()}
    quarantine_index = {row["inputIndex"] for row in expected["quarantines"]}
    defects = []
    for item in ledger:
        wanted = ledger_index.get(item["json"].get("eventId"))
        if item.get("pairedItem") != {"item": wanted}:
            defects.append((item["json"].get("eventId"), item.get("pairedItem"), wanted))
    for item in quarantine:
        wanted = item["json"].get("inputIndex")
        if wanted not in quarantine_index or item.get("pairedItem") != {"item": wanted}:
            defects.append((f"quarantine:{wanted}", item.get("pairedItem"), wanted))
    assert not defects, f"downstream item linkage is missing or points to the wrong input; examples: {defects[:5]}"
