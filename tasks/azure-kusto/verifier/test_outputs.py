from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import pytest


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
OUT = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results")) / "incident_report.json"


def _normalized_key(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())


def _pick(mapping: dict, *aliases: str):
    index = {_normalized_key(str(key)): value for key, value in mapping.items()}
    for alias in aliases:
        key = _normalized_key(alias)
        if key in index:
            return index[key]
    return None


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _as_float(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if cleaned.endswith("%"):
            try:
                return float(cleaned[:-1]) / 100.0
            except ValueError:
                return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _as_rate(value) -> float | None:
    number = _as_float(value)
    if number is not None and number > 1:
        number /= 100.0
    return number


def _as_time(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _metrics(rows: list[dict]) -> dict:
    failures = sum(row["Success"].strip().casefold() == "false" for row in rows)
    return {
        "request_count": len(rows),
        "error_count": failures,
        "error_rate": failures / len(rows),
        "p95_latency_ms": _percentile([float(row["DurationMs"]) for row in rows], 0.95),
    }


@lru_cache(maxsize=1)
def expected() -> dict:
    telemetry = _read_csv("request_telemetry.csv")
    deployments = _read_csv("deployments.csv")
    objectives = {
        row["Service"]: (float(row["TargetP95Ms"]), float(row["MaxErrorRate"]))
        for row in _read_csv("service_objectives.csv")
    }
    for row in telemetry:
        timestamp = _as_time(row["Timestamp"])
        assert timestamp is not None
        row["_time"] = timestamp
        row["_hour"] = timestamp.replace(minute=0, second=0, microsecond=0)

    hourly = defaultdict(list)
    for row in telemetry:
        hourly[(row["Service"], row["Region"], row["_hour"])].append(row)
    grouped = defaultdict(list)
    for (service, region, hour), rows in hourly.items():
        current = _metrics(rows)
        target_p95, max_error = objectives[service]
        grouped[(service, region)].append(
            (hour, current["p95_latency_ms"] > target_p95 and current["error_rate"] > max_error)
        )

    candidates = []
    for (service, region), bins in grouped.items():
        bins.sort()
        run_start = None
        for index, (hour, breach) in enumerate(bins):
            if breach and run_start is None:
                run_start = hour
            next_hour = bins[index + 1][0] if index + 1 < len(bins) else hour + timedelta(hours=1)
            next_breach = bins[index + 1][1] if index + 1 < len(bins) else False
            if run_start is not None and (not next_breach or next_hour != hour + timedelta(hours=1)):
                end = hour + timedelta(hours=1)
                if end - run_start >= timedelta(hours=2):
                    candidates.append((service, region, run_start, end))
                run_start = None
    assert candidates, "frozen fixture has no sustained dual-objective incident"

    def impact(candidate):
        service, region, start, end = candidate
        rows = [
            row
            for row in telemetry
            if row["Service"] == service
            and row["Region"] == region
            and start <= row["_time"] < end
        ]
        values = _metrics(rows)
        return values["error_count"], values["p95_latency_ms"]

    service, region, start, end = max(candidates, key=impact)
    baseline_start = start - (end - start)
    incident_rows = [
        row
        for row in telemetry
        if row["Service"] == service
        and row["Region"] == region
        and start <= row["_time"] < end
    ]
    baseline_rows = [
        row
        for row in telemetry
        if row["Service"] == service
        and row["Region"] == region
        and baseline_start <= row["_time"] < start
    ]
    endpoints = defaultdict(list)
    for row in incident_rows:
        endpoints[row["Endpoint"]].append(row)
    top_endpoint = max(
        endpoints,
        key=lambda endpoint: (
            sum(row["Success"].casefold() == "false" for row in endpoints[endpoint]),
            _percentile([float(row["DurationMs"]) for row in endpoints[endpoint]], 0.95),
        ),
    )
    deployment_ids = {row["DeploymentId"] for row in incident_rows}
    assert len(deployment_ids) == 1
    deployment_id = next(iter(deployment_ids))
    deployment = next(row for row in deployments if row["DeploymentId"] == deployment_id)
    return {
        "service": service,
        "region": region,
        "start": start,
        "end": end,
        "baseline_start": baseline_start,
        "incident_metrics": _metrics(incident_rows),
        "baseline_metrics": _metrics(baseline_rows),
        "deployment_id": deployment_id,
        "version": deployment["Version"],
        "top_endpoint": top_endpoint,
    }


@lru_cache(maxsize=1)
def load_report() -> tuple[dict | None, str | None]:
    if not OUT.is_file():
        return None, f"requested artifact is missing: {OUT}"
    try:
        value = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"incident_report.json is unreadable or invalid JSON: {exc}"
    if not isinstance(value, dict):
        return None, "incident_report.json must contain a JSON object"
    return value, None


def _usable_report() -> dict:
    report, error = load_report()
    if error:
        pytest.skip(f"semantic checks skipped after the single artifact-readability failure: {error}")
    assert report is not None
    return report


def _finding(report: dict) -> dict:
    candidate = _pick(report, "primary_incident", "primary_finding", "incident", "finding")
    if isinstance(candidate, dict):
        return candidate
    return report


def _window(container: dict, *, baseline: bool = False) -> dict:
    if baseline:
        base = _as_dict(_pick(container, "baseline", "pre_incident_baseline", "preincident"))
        nested = _pick(base, "window", "time_window", "time_range", "period")
        return _as_dict(nested) or base
    nested = _pick(container, "window", "incident_window", "time_window", "time_range", "period")
    return _as_dict(nested) or container


def _metric_container(container: dict) -> dict:
    return _as_dict(_pick(container, "metrics", "metrics_incident", "incident_metrics", "summary")) or container


def _metric_values(container: dict) -> dict:
    values = _metric_container(container)
    return {
        "request_count": _as_float(_pick(values, "request_count", "requests", "total_requests", "count")),
        "error_count": _as_float(_pick(values, "error_count", "errors", "failed_requests", "failures")),
        "error_rate": _as_rate(_pick(values, "error_rate", "failure_rate", "error_percentage")),
        "p95_latency_ms": _as_float(
            _pick(values, "p95_latency_ms", "p95_duration_ms", "p95_ms", "p95_latency", "p95")
        ),
    }


def test_primary_incident_identification():
    """The sustained dual-objective incident and its boundaries are correctly selected."""
    report = _usable_report()
    finding = _finding(report)
    truth = expected()
    window = _window(finding) or _window(report)
    service = _pick(finding, "service", "affected_service", "impacted_service")
    region = _pick(finding, "region", "affected_region", "impacted_region")
    actual_start = _as_time(_pick(window, "start", "start_utc", "start_time", "from"))
    actual_end = _as_time(_pick(window, "end", "end_utc", "end_time", "to"))
    assert str(service).casefold() == truth["service"].casefold(), (
        "the selected service is not the sustained customer-impacting regression"
    )
    assert str(region).casefold() == truth["region"].casefold(), (
        "the selected region is not where the sustained deployment regression occurs"
    )
    assert actual_start == truth["start"] and actual_end == truth["end"], (
        "incident boundaries must cover the consecutive breach hours and stop at recovery"
    )


def test_incident_and_baseline_metrics():
    """Incident and equal-length pre-incident metrics agree with the frozen telemetry."""
    report = _usable_report()
    finding = _finding(report)
    truth = expected()
    incident = _metric_values(finding)
    baseline_obj = _as_dict(_pick(finding, "baseline", "metrics_baseline", "pre_incident_baseline", "preincident"))
    if not baseline_obj:
        baseline_obj = _as_dict(_pick(report, "baseline", "pre_incident_baseline", "preincident"))
    baseline = _metric_values(baseline_obj)
    baseline_window = _window(finding, baseline=True)
    if not baseline_window:
        baseline_window = _window(report, baseline=True)

    assert int(incident["request_count"] or -1) == truth["incident_metrics"]["request_count"]
    assert incident["error_rate"] == pytest.approx(truth["incident_metrics"]["error_rate"], abs=0.0015)
    assert incident["p95_latency_ms"] == pytest.approx(
        truth["incident_metrics"]["p95_latency_ms"], abs=8.0
    )
    assert _as_time(_pick(baseline_window, "start", "start_utc", "start_time", "from")) == truth["baseline_start"]
    assert _as_time(_pick(baseline_window, "end", "end_utc", "end_time", "to")) == truth["start"]
    assert int(baseline["request_count"] or -1) == truth["baseline_metrics"]["request_count"]
    assert baseline["error_rate"] == pytest.approx(truth["baseline_metrics"]["error_rate"], abs=0.0015)
    assert baseline["p95_latency_ms"] == pytest.approx(
        truth["baseline_metrics"]["p95_latency_ms"], abs=8.0
    )


def test_deployment_and_endpoint_correlation():
    """The incident is consistently tied to the matching deployment and affected endpoint."""
    report = _usable_report()
    finding = _finding(report)
    truth = expected()
    deployment = _as_dict(_pick(finding, "deployment", "matching_deployment", "release"))
    deployment_id = _pick(deployment, "id", "deployment_id", "deploymentid") or _pick(
        finding, "deployment_id", "deploymentid"
    )
    version = _pick(deployment, "version", "release_version") or _pick(
        finding, "version", "deployment_version"
    )
    endpoint = _pick(
        finding,
        "top_affected_endpoint",
        "top_endpoint",
        "affected_endpoint",
        "endpoint",
    )
    assert str(deployment_id).casefold() == truth["deployment_id"].casefold(), (
        "the report points at the wrong deployment for requests in the incident window"
    )
    assert str(version).casefold() == truth["version"].casefold(), (
        "the deployment version does not reconcile with the deployment table"
    )
    if isinstance(endpoint, dict):
        endpoint = _pick(endpoint, "endpoint", "path", "route", "name")
    assert str(endpoint).casefold() == truth["top_endpoint"].casefold(), (
        "the named endpoint is not the one with the most incident failures"
    )
