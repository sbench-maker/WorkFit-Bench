from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

import pytest


REPORT = Path(os.environ.get("TASK_REPORT_PATH", "/root/results/incident_report.json"))
DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
HOUR_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})[T ](\d{2})")


def _canonical(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, path + (str(index),))


def _read_jsonl(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _read_report_for_semantics() -> dict:
    if not REPORT.is_file():
        pytest.skip("semantic checks blocked by the missing artifact already covered by artifact_usability")
    try:
        value = json.loads(REPORT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pytest.skip("semantic checks blocked by unreadable JSON already covered by artifact_usability")
    if not isinstance(value, dict):
        pytest.skip("semantic checks blocked by a non-object report already covered by artifact_usability")
    return value


def _all_strings(value: Any) -> list[str]:
    return [child for _, child in _walk(value) if isinstance(child, str)]


def _hour(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    match = HOUR_PATTERN.search(value)
    if not match:
        return None
    return f"{match.group(1)}T{match.group(2)}:00:00Z"


def _direct_value(node: dict, aliases: tuple[str, ...], *, exclude: tuple[str, ...] = ()) -> Any:
    canonical_aliases = tuple(_canonical(alias) for alias in aliases)
    for key, value in node.items():
        normalized = _canonical(key)
        if any(blocked in normalized for blocked in exclude):
            continue
        if any(normalized == alias or normalized.endswith(alias) or alias in normalized for alias in canonical_aliases):
            return value
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        candidate = value.strip().replace(",", "")
        if re.fullmatch(r"-?\d+(?:\.\d+)?", candidate):
            return float(candidate)
    return None


def _extract_hourly(report: dict) -> dict[str, dict[str, int]]:
    extracted: dict[str, dict[str, int]] = {}
    for path, node in _walk(report):
        if not isinstance(node, dict):
            continue
        raw_time = _direct_value(
            node,
            ("hour", "hour_start", "bucket", "bucket_start", "time_bucket", "timestamp", "interval_start"),
        )
        bucket = _hour(raw_time)
        if bucket is None and path:
            bucket = _hour(path[-1])
        if bucket is None:
            continue
        raw_bytes = _direct_value(
            node,
            ("src_reporter_bytes_to_payment", "traffic_bytes", "bytes_sent", "total_bytes", "bytes"),
            exclude=("rate", "percent", "pct"),
        )
        raw_drops = _direct_value(
            node,
            ("dropped_allocations", "nat_drops", "drop_count", "drops"),
            exclude=("rate", "percent", "pct"),
        )
        bytes_value = _number(raw_bytes)
        drops_value = _number(raw_drops)
        if bytes_value is not None and drops_value is not None:
            extracted[bucket] = {"bytes": int(bytes_value), "drops": int(drops_value)}
    return extracted


def _extract_source_drops(report: dict) -> dict[str, int]:
    candidates: dict[str, int] = {}
    for _, node in _walk(report):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            if IP_PATTERN.fullmatch(str(key)) and _number(value) is not None:
                candidates[str(key)] = int(_number(value) or 0)
        raw_ip = _direct_value(node, ("internal_ip", "source_ip", "src_ip", "ip_address", "ip"))
        if not isinstance(raw_ip, str) or not IP_PATTERN.fullmatch(raw_ip):
            continue
        raw_drops = _direct_value(
            node,
            ("dropped_allocations", "nat_drops", "drop_count", "drops"),
            exclude=("rate", "percent", "pct"),
        )
        drop_count = _number(raw_drops)
        if drop_count is not None:
            candidates[raw_ip] = max(candidates.get(raw_ip, 0), int(drop_count))
    return candidates


def _numeric_values_with_path(report: dict, groups: tuple[tuple[str, ...], ...]) -> list[float]:
    values = []
    for path, value in _walk(report):
        numeric = _number(value)
        if numeric is None:
            continue
        normalized_path = _canonical("/".join(path))
        if all(any(_canonical(token) in normalized_path for token in group) for group in groups):
            values.append(numeric)
    return values


def _expected() -> dict:
    context = json.loads((DATA / "incident_context.json").read_text(encoding="utf-8"))
    start, end = context["window_start"], context["window_end"]
    destination_ip = context["destination"]["ip"]
    destination_port = context["destination"]["port"]
    gateway = context["suspected_nat_gateway"]

    hourly_bytes: Counter[str] = Counter()
    for row in _read_jsonl("vpc_flow_logs.jsonl"):
        payload = row["json_payload"]
        connection = payload["connection"]
        if (
            start <= row["timestamp"] < end
            and payload["reporter"].upper() == "SRC"
            and connection["dest_ip"] == destination_ip
            and connection["dest_port"] == destination_port
        ):
            hourly_bytes[_hour(row["timestamp"])] += int(payload["bytes_sent"])

    hourly_drops: Counter[str] = Counter()
    source_drops: Counter[str] = Counter()
    for row in _read_jsonl("nat_logs.jsonl"):
        payload = row["json_payload"]
        details = payload["gateway_details"]
        if not start <= row["timestamp"] < end:
            continue
        if details["gateway_name"] != gateway or payload["connection"]["dest_ip"] != destination_ip:
            continue
        if payload["allocation_status"] == "DROPPED":
            hourly_drops[_hour(row["timestamp"])] += 1
            source_drops[details["internal_ip"]] += 1

    matching_denies = 0
    for row in _read_jsonl("firewall_logs.jsonl"):
        payload = row["json_payload"]
        connection = payload["connection"]
        if (
            start <= row["timestamp"] < end
            and connection["dest_ip"] == destination_ip
            and connection["dest_port"] == destination_port
            and payload["rule_details"]["action"] == "DENY"
        ):
            matching_denies += 1

    rtt_values = [
        float(row["p95"])
        for row in _read_jsonl("network_metrics.jsonl")
        if start <= row["timestamp"] < end
        and row["metric_type"] == "networking.googleapis.com/vm_flow/external_rtt"
        and row["metric_labels"].get("remote_ip") == destination_ip
    ]
    return {
        "context": context,
        "hourly": {
            hour: {"bytes": hourly_bytes[hour], "drops": hourly_drops[hour]}
            for hour in sorted(hourly_bytes)
        },
        "top_sources": source_drops.most_common(3),
        "matching_denies": matching_denies,
        "rtt_p95_max": max(rtt_values),
    }


def test_primary_diagnosis_and_path() -> None:
    report = _read_report_for_semantics()
    expected = _expected()
    context = expected["context"]
    diagnostic_strings = []
    for path, value in _walk(report):
        if not isinstance(value, str):
            continue
        final_key = _canonical(path[-1]) if path else ""
        if any(token in final_key for token in ("cause", "diagnosis", "summary")):
            diagnostic_strings.append(value.lower())
    assert any(
        "nat" in value and ("exhaust" in value or ("allocation" in value and "drop" in value))
        for value in diagnostic_strings
    ), "the primary finding does not identify Cloud NAT port exhaustion/allocation drops"

    text = " ".join(_all_strings(report)).lower()
    required_values = [
        context["service"],
        context["suspected_nat_gateway"],
        context["destination"]["ip"],
    ]
    for value in required_values:
        assert value.lower() in text, f"the affected path omits {value}"
    assert str(context["destination"]["port"]) in json.dumps(report), "the affected path omits TCP/443"
    assert context["window_start"][:13].lower() in text and context["window_end"][:13].lower() in text, (
        "the report does not preserve the bounded incident window"
    )


def test_hourly_traffic_and_drop_trend() -> None:
    report = _read_report_for_semantics()
    expected = _expected()["hourly"]
    actual = _extract_hourly(report)
    assert set(expected).issubset(actual), (
        f"hourly trend is missing buckets: {sorted(set(expected) - set(actual))}"
    )
    for hour, expected_values in expected.items():
        assert actual[hour] == expected_values, (
            f"hourly traffic/drop values for {hour} are {actual[hour]}, expected {expected_values}; "
            "traffic must use one VPC reporter and drops must use matching NAT records"
        )


def test_top_impacted_sources() -> None:
    report = _read_report_for_semantics()
    expected = _expected()["top_sources"]
    actual = _extract_source_drops(report)
    assert len(actual) >= 3, "fewer than three internal sources have usable NAT drop counts"
    actual_top = sorted(actual.items(), key=lambda item: (-item[1], item[0]))[:3]
    assert actual_top == expected, (
        f"top impacted sources are {actual_top}, expected {expected}; metadata-less VMs must remain in the ranking by IP"
    )


def test_alternative_cause_evidence() -> None:
    report = _read_report_for_semantics()
    expected = _expected()
    firewall_values = _numeric_values_with_path(
        report,
        (("firewall",), ("deny", "denied", "denies")),
    )
    assert expected["matching_denies"] in firewall_values, (
        "the report does not provide the correct relevant firewall-deny count for payment TCP/443"
    )
    rtt_values = _numeric_values_with_path(
        report,
        (("rtt", "latency"), ("p95", "95"), ("max", "maximum")),
    )
    assert expected["rtt_p95_max"] in rtt_values, (
        "the report does not provide the correct maximum external p95 RTT used to exclude latency degradation"
    )
