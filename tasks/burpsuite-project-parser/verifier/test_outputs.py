from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from urllib.parse import unquote

import pytest


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("TASK_OUTPUT_FILE", "/root/results/output.json"))
PROJECT = DATA / "harbor_portal.burp"
MISSING = object()


def _token(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _field(row: dict, aliases: tuple[str, ...], default=MISSING):
    wanted = {_token(alias) for alias in aliases}
    for key, value in row.items():
        if _token(key) in wanted:
            return value
    if default is MISSING:
        raise KeyError(f"none of {aliases!r} is present")
    return default


def _section(root: object, aliases: tuple[str, ...]):
    wanted = {_token(alias) for alias in aliases}
    queue = [root]
    seen: set[int] = set()
    while queue:
        current = queue.pop(0)
        if not isinstance(current, dict) or id(current) in seen:
            continue
        seen.add(id(current))
        for key, value in current.items():
            if _token(key) in wanted:
                return value
        queue.extend(value for value in current.values() if isinstance(value, dict))
    return None


def _records(section: object) -> list[dict]:
    records: list[dict] = []

    def visit(node: object, keyed_id: str | None = None) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item)
            return
        if not isinstance(node, dict):
            return
        identifier = _field(node, ("finding_id", "audit_id", "issue_id", "id"), None)
        if identifier is not None or keyed_id is not None:
            row = dict(node)
            if identifier is None:
                row["finding_id"] = keyed_id
            records.append(row)
            return
        for key, value in node.items():
            inferred = str(key) if isinstance(value, dict) and re.fullmatch(r"F[-_ ]?\d{3}", str(key), re.I) else None
            visit(value, inferred)

    visit(section)
    return records


def _normalize_id(value: object) -> str | None:
    match = re.search(r"\bF[-_ ]?(\d{3})\b", str(value), re.I)
    return f"F-{match.group(1)}" if match else None


def _normalize_url(value: object) -> str:
    return unquote(str(value).strip().rstrip("/")).casefold()


def _normalized_urls(value: object) -> set[str]:
    values = value if isinstance(value, list) else [value]
    return {_normalize_url(item) for item in values if str(item).strip()}


def _normalize_disposition(value: object) -> str | None:
    if isinstance(value, dict):
        for alias in ("status", "disposition", "verdict", "assessment", "result"):
            nested = _field(value, (alias,), None)
            if nested is not None:
                normalized = _normalize_disposition(nested)
                if normalized is not None:
                    return normalized
    token = _token(value)
    if any(term in token for term in ("notreproduced", "falsepositive", "mitigated", "blocked", "rejected")):
        return "not_reproduced_or_mitigated"
    if any(term in token for term in (
        "needsmanual", "manualvalidation", "manualreview", "inconclusive", "unverified",
        "requiresvalidation", "needsvalidation", "cannotverify", "unconfirmed", "tentative",
    )):
        return "needs_manual_validation"
    if token in {"confirmed", "validated", "verified", "truepositive", "actionable"} or token.startswith("confirmed"):
        return "confirmed"
    return None


def _submission() -> dict:
    if not OUTPUT.is_file():
        return {"error": f"missing {OUTPUT}"}
    try:
        root = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"error": f"unreadable JSON: {exc}"}
    if not isinstance(root, dict):
        return {"error": "top-level JSON value is not an object"}
    section = _section(root, ("findings", "finding_list", "audit_findings", "triage", "issues", "results"))
    records = _records(section)
    by_id: dict[str, list[dict]] = {}
    for row in records:
        identifier = _normalize_id(_field(row, ("finding_id", "audit_id", "issue_id", "id"), ""))
        if identifier:
            by_id.setdefault(identifier, []).append(row)
    return {"root": root, "section": section, "records": records, "by_id": by_id}


def _source() -> tuple[dict[str, dict], set[str]]:
    connection = sqlite3.connect(f"file:{PROJECT}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    audits = {row["finding_id"]: dict(row) for row in connection.execute("SELECT * FROM audit_items")}
    traffic_ids = {row["record_id"] for row in connection.execute("SELECT record_id FROM traffic")}
    connection.close()
    return audits, traffic_ids


def _require_usable(submission: dict) -> None:
    if submission.get("error") or not submission.get("records"):
        pytest.skip("artifact parse/collection failure is scored only by test_artifact_usability")


def _row_text(row: dict) -> str:
    return json.dumps(row, ensure_ascii=False).casefold()


def _evidence_value(row: dict):
    return _field(row, ("traffic_evidence", "evidence", "corroboration", "traffic", "observations", "proof"), None)


EXPECTED_DISPOSITIONS = {
    "F-001": "confirmed", "F-002": "confirmed", "F-003": "needs_manual_validation",
    "F-004": "not_reproduced_or_mitigated", "F-005": "not_reproduced_or_mitigated",
    "F-006": "confirmed", "F-007": "confirmed", "F-008": "confirmed", "F-009": "confirmed",
    "F-010": "confirmed", "F-011": "needs_manual_validation", "F-012": "needs_manual_validation",
    "F-013": "confirmed", "F-014": "confirmed", "F-015": "not_reproduced_or_mitigated",
    "F-016": "not_reproduced_or_mitigated", "F-017": "confirmed", "F-018": "needs_manual_validation",
}

EXPECTED_TRAFFIC = {
    "F-001": "P-001", "F-002": "P-002", "F-003": "P-003", "F-004": "P-004",
    "F-005": "P-005", "F-006": "P-006", "F-007": "P-007", "F-008": "P-007",
    "F-009": "P-001", "F-010": "P-010", "F-011": "P-011", "F-012": "P-012",
    "F-013": "P-013", "F-014": "P-014", "F-015": "P-015", "F-016": "P-016",
    "F-017": "P-017",
}

EVIDENCE_SIGNATURES = {
    "F-001": (("500", "database"), ("quote", "error")),
    "F-002": (("access-control-allow-origin", "credentials"), ("origin", "reflected")),
    "F-003": (("queued", "no"), ("202", "callback")),
    "F-004": (("encoded", "script"), ("escaped", "html")),
    "F-005": (("path", "rejected"), ("400", "validation")),
    "F-006": (("http", "redirect"), ("cleartext", "post")),
    "F-007": (("content-security-policy", "missing"), ("csp", "absent")),
    "F-008": (("strict-transport-security", "missing"), ("hsts", "absent")),
    "F-009": (("stack", "trace"), ("java", "line")),
    "F-010": (("__schema", "200"), ("introspection", "returned")),
    "F-011": (("gzip", "encoded"), ("body", "unavailable")),
    "F-012": (("scheduled", "no"), ("callback", "absent")),
    "F-013": (("x-frame-options", "missing"), ("frame-ancestors", "absent")),
    "F-014": (("debug", "build"), ("deployment", "metadata")),
    "F-015": (("external entit", "disabled"), ("xml", "rejected")),
    "F-016": (("no-store", "private"), ("cache", "contradict")),
    "F-017": (("location", "outside.invalid"), ("cross-site", "redirect")),
}


def _has_substantive_evidence(finding_id: str, row: dict) -> bool:
    evidence = _evidence_value(row)
    text = json.dumps(evidence, ensure_ascii=False).casefold() if evidence is not None else ""
    if EXPECTED_TRAFFIC[finding_id].casefold() in text:
        return True
    return any(all(term in text for term in signature) for signature in EVIDENCE_SIGNATURES[finding_id])


def _excerpt_strings(node: object, parent_key: str = "") -> list[str]:
    values: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            token = _token(key)
            if isinstance(value, str) and any(term in token for term in ("body", "excerpt", "snippet", "sample")):
                values.append(value)
            else:
                values.extend(_excerpt_strings(value, str(key)))
    elif isinstance(node, list):
        for value in node:
            values.extend(_excerpt_strings(value, parent_key))
    return values


def test_audit_scope_and_source_facts():
    submission = _submission()
    _require_usable(submission)
    audits, _ = _source()
    by_id = submission["by_id"]
    missing = sorted(set(audits) - set(by_id))
    duplicates = sorted(identifier for identifier in audits if len(by_id.get(identifier, [])) > 1)
    fact_errors: list[str] = []
    for finding_id, source in audits.items():
        if len(by_id.get(finding_id, [])) != 1:
            continue
        row = by_id[finding_id][0]
        severity = str(_field(row, ("severity", "risk_severity", "burp_severity"), "")).casefold()
        confidence = str(_field(row, ("confidence", "certainty", "burp_confidence"), "")).casefold()
        url = _field(row, ("affected_url", "affected_urls", "urls", "url", "endpoint", "location"), "")
        if severity != source["severity"].casefold():
            fact_errors.append(f"{finding_id} severity")
        if confidence != source["confidence"].casefold():
            fact_errors.append(f"{finding_id} confidence")
        if _normalize_url(source["url"]) not in _normalized_urls(url):
            fact_errors.append(f"{finding_id} URL")
    assert not missing and not duplicates and not fact_errors, (
        f"audit inventory mismatch; missing={missing}, duplicates={duplicates}, source_fact_errors={fact_errors}"
    )


def test_evidence_based_dispositions():
    submission = _submission()
    _require_usable(submission)
    errors: list[str] = []
    for finding_id, expected in EXPECTED_DISPOSITIONS.items():
        rows = submission["by_id"].get(finding_id, [])
        if len(rows) != 1:
            # Missing/duplicate records belong to the separate scope criterion.
            continue
        actual = _normalize_disposition(_field(rows[0], ("disposition", "status", "triage", "assessment", "verdict"), ""))
        if actual != expected:
            errors.append(f"{finding_id}={actual or 'unrecognized'} (expected {expected})")
    assert not errors, "dispositions do not follow decisive traffic or evidence gaps: " + "; ".join(errors)


def test_traffic_evidence_integrity_and_excerpt_limits():
    submission = _submission()
    _require_usable(submission)
    _, valid_traffic_ids = _source()
    substantive: list[str] = []
    cited_ids: set[str] = set()
    for finding_id in EXPECTED_TRAFFIC:
        rows = submission["by_id"].get(finding_id, [])
        if len(rows) == 1 and _has_substantive_evidence(finding_id, rows[0]):
            substantive.append(finding_id)
        if len(rows) == 1:
            evidence = _evidence_value(rows[0])
            if evidence is not None:
                cited_ids.update(re.findall(r"\b[PS]-\d{3}\b", json.dumps(evidence, ensure_ascii=False), re.I))
    invalid_ids = sorted(identifier.upper() for identifier in cited_ids if identifier.upper() not in valid_traffic_ids)
    excerpts = _excerpt_strings(submission["root"])
    oversized = [len(value) for value in excerpts if len(value) > 1000]
    assert len(substantive) >= 15 and not invalid_ids and not oversized, (
        f"traffic evidence is not reliable: substantive={len(substantive)}/17, "
        f"nonexistent_record_ids={invalid_ids}, body_excerpt_lengths_over_1000={oversized}"
    )


def test_capture_and_encoding_limitations():
    submission = _submission()
    _require_usable(submission)
    text = _row_text(submission["root"])
    admin_gap = "admin.harbor.test" in text and any(term in text for term in ("not captured", "absent", "excluded", "outside", "missing"))
    encoded_gap = "gzip" in text and any(term in text for term in ("encoded", "cannot", "unavailable", "inspect", "decode"))
    capture_caveat = any(term in text for term in ("incomplete capture", "capture is incomplete", "absence of traffic", "not proof", "proxy traffic is absent"))
    assert admin_gap and encoded_gap and capture_caveat, (
        "the triage must disclose the admin-host capture gap, gzip body limitation, and that absent traffic is not proof of safety"
    )
