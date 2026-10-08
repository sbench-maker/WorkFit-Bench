from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


DATA = Path(os.environ.get("SKILLSBENCH_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("SKILLSBENCH_OUTPUT_PATH", "/root/results/output.json"))
if not DATA.is_absolute() or not OUTPUT.is_absolute():
    raise ValueError("Verifier data and output paths must be absolute")

PRIMARY_KEYS = {
    "amazon_product": "product_id",
    "youtube_comments": "comment_id",
    "instagram_posts": "post_id",
    "google_maps_reviews": "review_id",
    "linkedin_job_listings": "job_id",
}
REQUEST_ID_ALIASES = ("request_id", "requestId", "request", "id", "job_id")
STATUS_ALIASES = ("status", "state", "outcome", "result_status")
RECORD_ALIASES = ("records", "data", "items", "results", "payload", "extracted_records")
ERROR_ALIASES = ("error", "message", "reason", "failure_reason", "details")


def norm_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def alias_value(mapping: dict, aliases: tuple[str, ...]) -> Any:
    by_key = {norm_key(key): value for key, value in mapping.items()}
    for alias in aliases:
        if norm_key(alias) in by_key:
            return by_key[norm_key(alias)]
    return None


def load_output() -> tuple[Any | None, str | None]:
    if not OUTPUT.is_file():
        return None, f"The requested artifact does not exist at {OUTPUT}."
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"The requested artifact is not readable JSON: {exc}."
    return payload, None


def all_nodes(value: Any):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from all_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_nodes(child)


def find_jobs(payload: Any, expected_ids: set[str]) -> list[dict]:
    candidates: list[list[dict]] = []
    for node in all_nodes(payload):
        if isinstance(node, list) and node and all(isinstance(item, dict) for item in node):
            candidates.append(node)
        elif isinstance(node, dict) and set(node).intersection(expected_ids):
            rows = []
            for key, value in node.items():
                if key in expected_ids and isinstance(value, dict):
                    row = dict(value)
                    row.setdefault("request_id", key)
                    rows.append(row)
            if rows:
                candidates.append(rows)
    if not candidates:
        return []
    return max(
        candidates,
        key=lambda rows: sum(str(alias_value(row, REQUEST_ID_ALIASES)) in expected_ids for row in rows),
    )


SUMMARY_ALIASES = {
    "total_requests": ("total_requests", "request_total", "total", "jobs_total"),
    "completed_requests": ("completed_requests", "completed", "succeeded", "successful_requests"),
    "failed_requests": ("failed_requests", "failed", "errors", "failure_count"),
    "timed_out_requests": ("timed_out_requests", "timed_out", "timeouts", "timeout_requests"),
    "total_records": ("total_records", "record_total", "records", "extracted_records"),
}


def find_summary(payload: Any) -> dict:
    candidates = []
    for node in all_nodes(payload):
        if not isinstance(node, dict):
            continue
        hits = sum(alias_value(node, aliases) is not None for aliases in SUMMARY_ALIASES.values())
        if hits:
            candidates.append((hits, node))
    return max(candidates, key=lambda item: item[0])[1] if candidates else {}


def normalize_status(value: object) -> str:
    text = norm_key(value)
    if text in {"complete", "completed", "success", "succeeded", "ready", "usable"}:
        return "completed"
    if text in {"failed", "failure", "error", "rejected", "triggerrejected", "triggererror", "collectionfailed"}:
        return "failed"
    if text in {"timeout", "timedout", "expired", "unfinished"}:
        return "timed_out"
    return text


def extract_records(job: dict) -> list[dict]:
    value = alias_value(job, RECORD_ALIASES)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for nested_alias in RECORD_ALIASES:
            nested = alias_value(value, (nested_alias,))
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
        return [value]
    return []


def canonical_record(record: dict) -> dict[str, Any]:
    def visit(value: Any) -> Any:
        if isinstance(value, dict):
            return {norm_key(key): visit(child) for key, child in value.items()}
        if isinstance(value, list):
            return [visit(child) for child in value]
        return value
    return visit(record)


def truth() -> dict:
    requests = json.loads((DATA / "feed_requests.json").read_text(encoding="utf-8"))["requests"]
    entries = json.loads((DATA / "api_catalog.json").read_text(encoding="utf-8"))["entries"]
    entry_by_id = {row["request_id"]: row for row in entries}
    jobs = {}
    for request in requests:
        entry = entry_by_id[request["request_id"]]
        terminal = entry["terminal"]
        status = "completed" if terminal == "complete" else "timed_out" if terminal == "timeout" else "failed"
        records: list[dict] = []
        if status == "completed":
            key = PRIMARY_KEYS[request["dataset_type"]]
            latest = {}
            for record in entry["records"]:
                latest[str(record[key])] = record
            records = list(latest.values())
        jobs[request["request_id"]] = {
            "dataset_type": request["dataset_type"],
            "status": status,
            "records": records,
            "error": entry["error"],
        }
    summary = {
        "total_requests": len(requests),
        "completed_requests": sum(row["status"] == "completed" for row in jobs.values()),
        "failed_requests": sum(row["status"] == "failed" for row in jobs.values()),
        "timed_out_requests": sum(row["status"] == "timed_out" for row in jobs.values()),
        "total_records": sum(len(row["records"]) for row in jobs.values()),
    }
    return {"jobs": jobs, "summary": summary}


TRUTH = truth()


def normalized_submission() -> tuple[Any | None, list[dict], dict, str | None]:
    payload, error = load_output()
    if error:
        return payload, [], {}, error
    jobs = find_jobs(payload, set(TRUTH["jobs"]))
    return payload, jobs, find_summary(payload), None


def jobs_by_id(rows: list[dict]) -> tuple[dict[str, dict], Counter]:
    ids = [str(alias_value(row, REQUEST_ID_ALIASES)) for row in rows]
    return {request_id: row for request_id, row in zip(ids, rows)}, Counter(ids)


def test_request_ledger_and_terminal_states():
    _, jobs, _, error = normalized_submission()
    assert error is None, error
    actual, counts = jobs_by_id(jobs)
    expected_ids = set(TRUTH["jobs"])
    assert set(actual) == expected_ids, (
        f"The request ledger is incomplete: missing={sorted(expected_ids - set(actual))}, "
        f"unexpected={sorted(set(actual) - expected_ids)}."
    )
    duplicates = sorted(request_id for request_id, count in counts.items() if count != 1)
    assert not duplicates, f"Request IDs must appear once in the collection ledger; repeated IDs: {duplicates}."
    wrong = {
        request_id: normalize_status(alias_value(actual[request_id], STATUS_ALIASES))
        for request_id in expected_ids
        if normalize_status(alias_value(actual[request_id], STATUS_ALIASES)) != TRUTH["jobs"][request_id]["status"]
    }
    assert not wrong, f"Terminal outcomes are wrong for these requests: {wrong}."


def test_completed_record_coverage_and_deduplication():
    _, jobs, _, error = normalized_submission()
    assert error is None, error
    actual, _ = jobs_by_id(jobs)
    problems = []
    for request_id, expected_job in TRUTH["jobs"].items():
        if request_id not in actual:
            problems.append(f"{request_id}: request missing")
            continue
        records = extract_records(actual[request_id])
        if expected_job["status"] != "completed":
            if records:
                problems.append(f"{request_id}: non-completed job contains {len(records)} extracted records")
            continue
        key = PRIMARY_KEYS[expected_job["dataset_type"]]
        canonical_key = norm_key(key)
        actual_ids = [str(canonical_record(record).get(canonical_key)) for record in records]
        expected_ids = [str(record[key]) for record in expected_job["records"]]
        if Counter(actual_ids) != Counter(expected_ids):
            missing = sorted(set(expected_ids) - set(actual_ids))[:6]
            unexpected = sorted(set(actual_ids) - set(expected_ids))[:6]
            repeated = sorted(record_id for record_id, count in Counter(actual_ids).items() if count > 1)[:6]
            problems.append(
                f"{request_id}: missing={missing}, unexpected={unexpected}, repeated={repeated}, "
                f"actual_count={len(actual_ids)}, expected_count={len(expected_ids)}"
            )
    assert not problems, "Record coverage or deduplication is wrong:\n" + "\n".join(problems)


def test_extracted_field_fidelity():
    _, jobs, _, error = normalized_submission()
    assert error is None, error
    actual, _ = jobs_by_id(jobs)
    mismatches = []
    for request_id, expected_job in TRUTH["jobs"].items():
        if expected_job["status"] != "completed" or request_id not in actual:
            continue
        key = PRIMARY_KEYS[expected_job["dataset_type"]]
        canonical_key = norm_key(key)
        actual_by_id = {
            str(canonical_record(record).get(canonical_key)): canonical_record(record)
            for record in extract_records(actual[request_id])
        }
        for expected_record in expected_job["records"]:
            record_id = str(expected_record[key])
            observed = actual_by_id.get(record_id)
            if observed is None:
                continue
            expected = canonical_record(expected_record)
            wrong_fields = [field for field, value in expected.items() if field not in observed or observed[field] != value]
            if wrong_fields:
                mismatches.append(f"{request_id}/{record_id}: {wrong_fields[:5]}")
                if len(mismatches) >= 12:
                    break
        if len(mismatches) >= 12:
            break
    assert not mismatches, (
        "Extracted website-specific values do not match the final service records (including updated repeats):\n"
        + "\n".join(mismatches)
    )


def test_summary_reconciliation_and_failure_transparency():
    _, jobs, summary, error = normalized_submission()
    assert error is None, error
    actual, _ = jobs_by_id(jobs)
    wrong_summary = {}
    for field, expected in TRUTH["summary"].items():
        value = alias_value(summary, SUMMARY_ALIASES[field])
        try:
            observed = int(value)
        except (TypeError, ValueError):
            observed = None
        if observed != expected:
            wrong_summary[field] = {"observed": value, "expected": expected}
    assert not wrong_summary, f"The compact collection summary does not reconcile: {wrong_summary}."
    missing_errors = []
    for request_id, expected_job in TRUTH["jobs"].items():
        if expected_job["status"] == "completed" or request_id not in actual:
            continue
        reason = alias_value(actual[request_id], ERROR_ALIASES)
        if not isinstance(reason, str) or not reason.strip():
            missing_errors.append(request_id)
    assert not missing_errors, (
        f"Failed or timed-out jobs lack a usable error/reason: {missing_errors}; users could mistake them for empty feeds."
    )
