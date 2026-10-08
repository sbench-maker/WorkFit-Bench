from __future__ import annotations

import json
import posixpath
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import unquote


DATA_DIR = Path("/root/data")
OUTPUT_PATH = Path("/root/results/output.json")
SEVERITY = {"none": 0, "note": 1, "warning": 2, "error": 3}
STATUSES = ("new", "fixed", "unchanged")
STATUS_ALIASES = {
    "new": {"new", "added", "introduced", "newfinding", "newfindings"},
    "fixed": {"fixed", "resolved", "removed", "fixedfinding", "fixedfindings"},
    "unchanged": {"unchanged", "existing", "persistent", "carriedover", "unchangedfinding", "unchangedfindings"},
}


def token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def clean_uri(value: str) -> str:
    value = unquote(value or "").replace("\\", "/")
    if value.lower().startswith("file://"):
        value = value[7:]
    return value


def normalize_source_path(uri: str, base_uri: str | None, repository_prefix: str) -> str:
    value = clean_uri(uri)
    prefix = clean_uri(repository_prefix)
    if base_uri and not value.startswith("/") and not re.match(r"^[A-Za-z]:/", value):
        value = clean_uri(base_uri).rstrip("/") + "/" + value
    value = posixpath.normpath(value)
    prefix = posixpath.normpath(prefix)
    if value.casefold().startswith(prefix.rstrip("/").casefold() + "/"):
        value = value[len(prefix.rstrip("/")) + 1 :]
    return value.lstrip("./").lstrip("/")


def normalize_submitted_path(value: Any) -> str:
    path = unquote(str(value or "")).replace("\\", "/")
    if path.startswith("./"):
        path = path[2:]
    return posixpath.normpath(path)


def source_rule_id(result: dict, rules: list[dict]) -> str:
    if result.get("ruleId"):
        return str(result["ruleId"])
    index = result.get("ruleIndex")
    if isinstance(index, int) and 0 <= index < len(rules):
        return str(rules[index].get("id", "unknown"))
    return "unknown"


def source_records(export: dict, manifest_entry: dict) -> list[dict]:
    records = []
    for run in export.get("runs", []):
        driver = run.get("tool", {}).get("driver", {})
        rules = driver.get("rules", []) or []
        bases = run.get("originalUriBaseIds", {}) or {}
        for result in run.get("results", []) or []:
            locations = result.get("locations") or []
            physical = locations[0].get("physicalLocation", {}) if locations else {}
            artifact = physical.get("artifactLocation", {}) or {}
            region = physical.get("region", {}) or {}
            base = bases.get(artifact.get("uriBaseId"), {}) if artifact.get("uriBaseId") else {}
            path = normalize_source_path(
                str(artifact.get("uri", "")), base.get("uri"), manifest_entry["repository_prefix"]
            )
            rule_id = source_rule_id(result, rules)
            line = region.get("startLine")
            partial = result.get("partialFingerprints") or {}
            full = result.get("fingerprints") or {}
            if partial.get("primaryLocationLineHash/v1"):
                identity = "fingerprint:" + str(partial["primaryLocationLineHash/v1"])
            elif full.get("matchBasedId/v1"):
                identity = "fingerprint:" + str(full["matchBasedId/v1"])
            else:
                identity = f"location:{rule_id}|{path}|{line}"
            message_obj = result.get("message") or {}
            records.append(
                {
                    "identity": identity,
                    "rule": rule_id,
                    "level": str(result.get("level", "warning")).lower(),
                    "message": str(message_obj.get("text") or message_obj.get("markdown") or ""),
                    "path": path,
                    "line": line,
                    "source": manifest_entry["file"],
                }
            )
    return records


def build_expected() -> tuple[dict[str, dict[str, dict]], dict[str, dict[str, int]], str]:
    manifest = json.loads((DATA_DIR / "scan_manifest.json").read_text(encoding="utf-8"))
    snapshots = {"baseline": [], "current": []}
    for entry in manifest["exports"]:
        payload = json.loads((DATA_DIR / entry["file"]).read_text(encoding="utf-8"))
        snapshots[entry["snapshot"]].extend(source_records(payload, entry))

    canonical = {}
    for snapshot, records in snapshots.items():
        groups: dict[str, list[dict]] = {}
        for record in records:
            groups.setdefault(record["identity"], []).append(record)
        canonical[snapshot] = {}
        for identity, copies in groups.items():
            copies.sort(
                key=lambda row: (
                    SEVERITY.get(row["level"], -1),
                    bool(row["path"]),
                    bool(row["message"]),
                    row["source"],
                ),
                reverse=True,
            )
            canonical[snapshot][identity] = copies[0]

    baseline, current = canonical["baseline"], canonical["current"]
    expected = {
        "new": {identity: current[identity] for identity in set(current) - set(baseline)},
        "fixed": {identity: baseline[identity] for identity in set(baseline) - set(current)},
        "unchanged": {identity: current[identity] for identity in set(current) & set(baseline)},
    }
    counts = {
        status: {
            level: sum(row["level"] == level for row in rows.values())
            for level in SEVERITY
        }
        for status, rows in expected.items()
    }
    gate = "fail" if counts["new"]["error"] else "pass"
    return expected, counts, gate


def load_submission() -> tuple[Any | None, str | None]:
    if not OUTPUT_PATH.is_file():
        return None, f"missing requested artifact: {OUTPUT_PATH}"
    try:
        payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"output.json is not readable JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "output.json must have a JSON object at its root"
    return payload, None


def value_for(mapping: Any, aliases: set[str]) -> Any:
    if not isinstance(mapping, dict):
        return None
    for key, value in mapping.items():
        if token(key) in aliases:
            return value
    return None


def record_status(record: dict) -> str | None:
    raw = value_for(record, {"status", "state", "classification", "change", "changetype"})
    if raw is None:
        return None
    raw_token = token(raw)
    for status, aliases in STATUS_ALIASES.items():
        if raw_token in aliases:
            return status
    return None


def as_records(value: Any) -> list[dict] | None:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for alias in ({"items", "findings", "results", "alerts", "records", "details"},):
            nested = value_for(value, alias)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
        records = []
        for key, item in value.items():
            if isinstance(item, dict):
                copied = dict(item)
                if value_for(copied, {"identity", "fingerprint", "findingid", "canonicalid"}) is None:
                    copied["identity"] = key
                records.append(copied)
        return records if records else None
    return None


def extract_status_groups(payload: dict) -> dict[str, list[dict]] | None:
    containers = [payload]
    for key in ("findings", "results", "alerts", "comparison", "diff", "regression"):
        nested = value_for(payload, {token(key)})
        if isinstance(nested, (dict, list)):
            containers.append(nested)

    for container in containers:
        if isinstance(container, dict):
            groups = {}
            for status, aliases in STATUS_ALIASES.items():
                records = as_records(value_for(container, aliases))
                if records is not None:
                    groups[status] = records
            if set(groups) == set(STATUSES):
                return groups
        if isinstance(container, list):
            groups = {status: [] for status in STATUSES}
            for record in container:
                if isinstance(record, dict) and (status := record_status(record)):
                    groups[status].append(record)
            if any(groups.values()):
                return groups
    return None


def scalar_field(record: dict, aliases: set[str]) -> Any:
    direct = value_for(record, aliases)
    if direct is not None:
        if isinstance(direct, dict):
            nested = value_for(direct, aliases | {"id", "value", "name", "text"})
            return nested if nested is not None else direct
        return direct
    for container_name in ("location", "physicalLocation", "artifactLocation", "region", "rule", "details"):
        nested = value_for(record, {token(container_name)})
        if isinstance(nested, dict):
            found = value_for(nested, aliases)
            if found is not None:
                return found
            for child in nested.values():
                if isinstance(child, dict) and (found := value_for(child, aliases)) is not None:
                    return found
    return None


def submitted_identity(record: dict, locator: dict[tuple[str, str, int], str]) -> str | None:
    raw = scalar_field(record, {"identity", "fingerprint", "findingid", "canonicalid", "dedupkey"})
    if isinstance(raw, str) and raw:
        if raw.startswith(("fingerprint:", "location:")):
            return raw
        if raw.startswith(("nmb-", "legacy-")):
            return "fingerprint:" + raw
    rule = scalar_field(record, {"ruleid", "rule", "checkid", "rulecode"})
    path = scalar_field(record, {"path", "file", "filepath", "uri", "artifacturi"})
    line = scalar_field(record, {"line", "startline", "linenumber"})
    try:
        locator_key = (str(rule), normalize_submitted_path(path), int(line))
    except (TypeError, ValueError):
        return None
    return locator.get(locator_key)


def normalize_message(value: Any) -> str:
    text = re.sub(r"[*_`]", "", str(value or ""))
    return " ".join(text.split()).casefold()


def extract_severity_totals(payload: dict) -> dict[str, dict[str, int]] | None:
    candidates = []
    for container in (payload, value_for(payload, {"summary", "totals", "metrics", "statistics", "counts"})):
        if isinstance(container, dict):
            candidates.append(container)
            for aliases in (
                {"bystatusandseverity", "bystatusseverity", "severitybystatus", "severitytotals"},
                {"statuses", "statussummary"},
            ):
                nested = value_for(container, aliases)
                if isinstance(nested, dict):
                    candidates.append(nested)
    for candidate in candidates:
        parsed = {}
        for status, aliases in STATUS_ALIASES.items():
            row = value_for(candidate, aliases)
            if not isinstance(row, dict):
                break
            severity_map = value_for(row, {"byseverity", "severity", "severitycounts", "counts"})
            if isinstance(severity_map, dict):
                row = severity_map
            values = {}
            for level in SEVERITY:
                raw = value_for(row, {token(level)})
                try:
                    values[level] = int(raw) if raw is not None else 0
                except (TypeError, ValueError):
                    values[level] = -1
            parsed[status] = values
        if set(parsed) == set(STATUSES):
            return parsed

    for container in candidates:
        rows = value_for(container, {"severitytotals", "counts", "breakdown"})
        if isinstance(rows, list):
            parsed = {status: {level: 0 for level in SEVERITY} for status in STATUSES}
            seen = set()
            for row in rows:
                if not isinstance(row, dict):
                    continue
                status = record_status(row)
                level = token(value_for(row, {"severity", "level"}))
                count = value_for(row, {"count", "total", "value"})
                if status and level in SEVERITY:
                    try:
                        parsed[status][level] = int(count)
                        seen.add(status)
                    except (TypeError, ValueError):
                        pass
            if seen == set(STATUSES):
                return parsed
    return None


def extract_gate(payload: dict) -> str | None:
    candidates = [
        value_for(payload, {"gate", "releasegate", "cigate", "decision"}),
        value_for(value_for(payload, {"summary"}), {"gate", "releasegate", "cigate", "decision"}),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            candidate = value_for(candidate, {"status", "decision", "result", "outcome", "pass", "passed"})
        if isinstance(candidate, bool):
            return "pass" if candidate else "fail"
        if candidate is not None:
            normalized = token(candidate)
            if normalized in {"pass", "passed", "allow", "allowed", "success", "green"}:
                return "pass"
            if normalized in {"fail", "failed", "block", "blocked", "failure", "red"}:
                return "fail"
    return None


EXPECTED, EXPECTED_COUNTS, EXPECTED_GATE = build_expected()
LOCATOR = {
    (row["rule"], row["path"], int(row["line"])): identity
    for rows in EXPECTED.values()
    for identity, row in rows.items()
}


def test_artifact_usability():
    payload, error = load_submission()
    assert error is None, error
    groups = extract_status_groups(payload)
    assert groups is not None, (
        "output.json does not expose recognizable new, fixed, and unchanged finding collections"
    )
    assert extract_severity_totals(payload) is not None, (
        "output.json does not expose recognizable per-status severity totals"
    )
    assert extract_gate(payload) is not None, "output.json does not expose a recognizable pass/fail gate"


def test_comparison_and_deduplication():
    payload, error = load_submission()
    assert error is None, error
    groups = extract_status_groups(payload)
    assert groups is not None, "comparison groups are unavailable; see artifact usability"
    for status in STATUSES:
        identities = [submitted_identity(row, LOCATOR) for row in groups[status]]
        unresolved = sum(identity is None for identity in identities)
        assert unresolved == 0, (
            f"{status} contains {unresolved} findings that cannot be tied to a source identity by fingerprint or rule/path/line"
        )
        assert len(identities) == len(set(identities)), (
            f"{status} contains duplicate canonical findings, so repeated scanner results were not fully collapsed"
        )
        assert set(identities) == set(EXPECTED[status]), (
            f"{status} membership differs from the baseline/current comparison: "
            f"missing={len(set(EXPECTED[status]) - set(identities))}, "
            f"unexpected={len(set(identities) - set(EXPECTED[status]))}"
        )


def test_finding_fidelity():
    payload, error = load_submission()
    assert error is None, error
    groups = extract_status_groups(payload)
    assert groups is not None, "finding details are unavailable; see artifact usability"
    problems = []
    for status in STATUSES:
        for record in groups[status]:
            identity = submitted_identity(record, LOCATOR)
            if identity not in EXPECTED[status]:
                continue
            expected = EXPECTED[status][identity]
            rule = scalar_field(record, {"ruleid", "rule", "checkid", "rulecode"})
            level = scalar_field(record, {"level", "severity"})
            message = scalar_field(record, {"message", "text", "description"})
            path = scalar_field(record, {"path", "file", "filepath", "uri", "artifacturi"})
            line = scalar_field(record, {"line", "startline", "linenumber"})
            try:
                line_value = int(line)
            except (TypeError, ValueError):
                line_value = None
            checks = {
                "rule": str(rule or "") == expected["rule"],
                "severity": str(level or "").casefold() == expected["level"],
                "message": normalize_message(message) == normalize_message(expected["message"]),
                "normalized path": normalize_submitted_path(path) == expected["path"],
                "line": line_value == expected["line"],
            }
            for field, okay in checks.items():
                if not okay:
                    problems.append(f"{status}/{identity}: incorrect or missing {field}")
    assert not problems, (
        f"{len(problems)} traceability defects found; examples: " + "; ".join(problems[:8])
    )


def test_summaries_and_gate():
    payload, error = load_submission()
    assert error is None, error
    totals = extract_severity_totals(payload)
    assert totals is not None, "per-status severity totals are unavailable; see artifact usability"
    assert totals == EXPECTED_COUNTS, (
        f"severity totals do not reconcile to the canonical comparison: expected {EXPECTED_COUNTS}, got {totals}"
    )
    gate = extract_gate(payload)
    assert gate == EXPECTED_GATE, (
        f"release gate is {gate!r}, expected {EXPECTED_GATE!r} from the new error-level finding count"
    )
