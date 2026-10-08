from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path


OUT = Path(os.environ.get("TASK_OUTPUT_PATH", "/root/results/lineage_summary.md"))
DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))


def norm(value) -> str:
    value = unicodedata.normalize("NFKC", str(value)).casefold()
    value = value.replace("_", " ").replace("–", "-").replace("×", " x ")
    return " ".join(value.split())


def load_json(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def load_report() -> tuple[str, str | None]:
    if not OUT.is_file():
        return "", f"missing requested artifact: {OUT}"
    try:
        text = OUT.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return "", f"lineage report is not readable UTF-8 Markdown: {exc}"
    return text, None


def unique_export_rows(payload: dict, collection: str) -> list[dict]:
    id_key = {"entities": "entityId", "processes": "processId", "links": "linkId"}[collection]
    rows = {}
    for page in payload["response"]["pages"]:
        for row in page[collection]:
            key = row.get(id_key)
            if key is not None:
                rows[key] = row
    return list(rows.values())


def has_tokens_near(text: str, tokens: list[str], span: int = 260) -> bool:
    normalized = norm(text)
    wanted = [norm(token) for token in tokens]
    starts = [match.start() for match in re.finditer(re.escape(wanted[0]), normalized)]
    for start in starts:
        window = normalized[max(0, start - span // 3): start + span]
        if all(token in window for token in wanted[1:]):
            return True
    return False


def mentions(text: str, *aliases: str) -> bool:
    normalized = norm(text)
    return any(norm(alias) in normalized for alias in aliases)


def test_upstream_lineage_accuracy():
    report, error = load_report()
    assert error is None, error
    export = load_json("upstream_search_export.json")
    entities = {row["entityId"]: row for row in unique_export_rows(export, "entities")}
    links = [
        row for row in unique_export_rows(export, "links")
        if row.get("active") is True and row.get("endpointState") == "RESOLVED"
    ]
    source_ids = {row["source"]["entityId"] for row in links}
    target_ids = {row["target"]["entityId"] for row in links}
    roots = source_ids - target_ids
    failures = []
    if roots != {"E01", "E02", "E03", "E04"}:
        failures.append(f"fixture graph roots unexpectedly changed: {sorted(roots)}")

    root_tokens = {
        "E01": ["helios-ingest-eu", "billing", "invoices"],
        "E02": ["helios-crm", "raw_crm", "customer_contracts"],
        "E03": ["helios-fx", "reference", "daily_rates"],
        "E04": ["helios-finance", "raw_erp", "invoice_adjustments"],
    }
    for entity_id in roots:
        if not has_tokens_near(report, root_tokens[entity_id]):
            failures.append(f"confirmed ultimate source {entities[entity_id]['fullyQualifiedName']} is not clearly named")

    for asset in ("invoice_lines_stg", "customer_terms", "daily_fx", "invoice_adjustments_stg", "invoice_enriched"):
        if not mentions(report, asset):
            failures.append(f"material upstream asset {asset} is missing")

    for job in ("parse_invoice_files", "enrich_invoice_finance", "build_fct_invoice_daily"):
        if not mentions(report, job):
            failures.append(f"material upstream processing job {job} is missing")
    branch_jobs = sum(mentions(report, job) for job in (
        "normalize_customer_terms", "publish_daily_fx", "stage_invoice_adjustments"
    ))
    if branch_jobs < 2:
        failures.append("fewer than two of the three small branch-normalization jobs are named")

    if not has_tokens_near(report, ["gross_eur", "discount_amount", "adjustment_eur", "net_revenue"], span=420):
        failures.append("the three direct inputs to net_revenue are not connected in one understandable transform passage")
    transform_text = norm(report)
    subtract = any(term in transform_text for term in ("subtract", "minus", "less", "gross eur - discount amount"))
    add = any(term in transform_text for term in ("add adjustment", "plus adjustment", "+ adjustment amount", "+ adjustment eur"))
    if not subtract or not add:
        failures.append("the direct calculation does not preserve subtract-discount and add-adjustment semantics")
    assert not failures, "; ".join(failures)


def test_downstream_lineage_accuracy():
    report, error = load_report()
    assert error is None, error
    export = load_json("downstream_search_export.json")
    entities = {row["entityId"]: row for row in unique_export_rows(export, "entities")}
    links = [
        row for row in unique_export_rows(export, "links")
        if row.get("active") is True and row.get("endpointState") == "RESOLVED"
    ]
    source_ids = {row["source"]["entityId"] for row in links}
    target_ids = {row["target"]["entityId"] for row in links}
    leaves = target_ids - source_ids
    failures = []
    if leaves != {"E22", "E23", "E24", "E25"}:
        failures.append(f"fixture graph leaves unexpectedly changed: {sorted(leaves)}")

    for asset in ("daily_revenue_kpi", "invoice_quality_monitor"):
        if not mentions(report, asset):
            failures.append(f"immediate downstream product {asset} is missing")
    leaf_aliases = {
        "E22": [("looker", "Revenue Health"), ("finance-executive", "revenue-health")],
        "E23": [("revenue_forecast_features",)],
        "E24": [("finance-close", "daily-revenue"), ("finance close", "daily revenue")],
        "E25": [("collection_priority",)],
    }
    for entity_id in leaves:
        row = entities[entity_id]
        if not any(has_tokens_near(report, list(alias)) for alias in leaf_aliases[entity_id]):
            failures.append(f"current final consumer {row['fullyQualifiedName']} is not clearly named")

    for job in ("aggregate_daily_revenue", "publish_invoice_quality_monitor"):
        if not mentions(report, job):
            failures.append(f"material immediate downstream job {job} is missing")
    consumer_jobs = sum(mentions(report, job) for job in (
        "refresh_revenue_health_explore", "build_revenue_forecast_features",
        "export_finance_close_feed", "score_collection_priority"
    ))
    if consumer_jobs < 3:
        failures.append("fewer than three of the four small final-consumer jobs are named")
    assert not failures, "; ".join(failures)


def test_scope_limits_and_edge_cases():
    report, error = load_report()
    assert error is None, error
    upstream = load_json("upstream_search_export.json")
    downstream = load_json("downstream_search_export.json")
    location_snapshot = load_json("supported_locations_snapshot.json")
    request = upstream["request"]
    text = norm(report)
    failures = []

    if not has_tokens_near(report, ["column", "net_revenue", "scope"], span=320) and not has_tokens_near(report, ["column", "net_revenue", "limited"], span=320):
        failures.append("the report does not clearly limit analysis to the requested column")
    if norm(request["parent"]) not in text:
        failures.append("the parent location is missing or wrong")
    for location in location_snapshot["supportedPhysicalLocations"]:
        if norm(location) not in text:
            failures.append(f"searched location {location} is omitted")
    limits = request["limits"]
    if not re.search(rf"depth(?:\s+(?:limit|max(?:imum)?))?\D{{0,25}}{limits['maxDepth']}\b", text):
        failures.append("maxDepth is missing or wrong")
    if not re.search(rf"(?:(?:maximum|max)\s*results|results?\s+(?:limit|cap))\D{{0,25}}{limits['maxResults']}\b", text):
        failures.append("maxResults is missing or wrong")
    if not re.search(rf"process.{{0,24}}link.{{0,25}}{limits['maxProcessPerLink']}\b", text):
        failures.append("maxProcessPerLink is missing or wrong")
    if not all(direction in text for direction in ("upstream", "downstream")):
        failures.append("both frozen search directions are not stated")
    if upstream["response"]["truncated"] or downstream["response"]["truncated"]:
        failures.append("fixture search responses unexpectedly became truncated")
    elif not any(term in text for term in ("truncated: false", "not truncated", "untruncated", "report `truncated: false`")):
        failures.append("the captured response-completeness boundary is not stated")

    if not has_tokens_near(report, ["legacy_discount_v", "historical"], span=220) and not has_tokens_near(report, ["legacy_discount_v", "inactive"], span=220):
        failures.append("legacy_discount_v is not flagged as historical/inactive")
    old_path_flagged = any(
        has_tokens_near(report, [asset, state], span=220)
        for asset in ("old-revenue-daily", "old revenue daily")
        for state in ("historical", "inactive")
    )
    if not old_path_flagged:
        failures.append("old-revenue-daily is not flagged as historical/inactive")
    override_ok = (
        has_tokens_near(report, ["manual_revenue_override", "unresolved"], span=300)
        or has_tokens_near(report, ["manual_revenue_override", "unavailable"], span=300)
        or has_tokens_near(report, ["manual_revenue_override", "unconfirmed"], span=300)
        or has_tokens_near(report, ["manual_revenue_override", "metadata", "gap"], span=330)
    )
    if not override_ok:
        failures.append("the manual override endpoint is not flagged as incomplete or unresolved")
    assert not failures, "; ".join(failures)
