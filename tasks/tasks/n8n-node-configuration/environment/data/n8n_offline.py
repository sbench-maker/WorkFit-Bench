#!/usr/bin/env python3
"""Small offline stand-in for node discovery and workflow validation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def workflow_root(document: dict) -> dict:
    nested = document.get("workflow")
    return nested if isinstance(nested, dict) else document


def by_name(workflow: dict) -> dict[str, dict]:
    nodes = workflow.get("nodes", [])
    if not isinstance(nodes, list):
        return {}
    return {n.get("name"): n for n in nodes if isinstance(n, dict) and isinstance(n.get("name"), str)}


def deep_search(value: object, query: str, path: str = "") -> list[dict]:
    found: list[dict] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if query in str(key).lower() or (not isinstance(child, (dict, list)) and query in str(child).lower()):
                found.append({"path": child_path, "value": child})
            found.extend(deep_search(child, query, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(deep_search(child, query, f"{path}[{index}]"))
    return found


def configured_assignments(node: dict) -> dict[str, object]:
    parameters = node.get("parameters", {})
    outer = parameters.get("assignments", {}) if isinstance(parameters, dict) else {}
    rows = outer.get("assignments", []) if isinstance(outer, dict) else []
    result = {}
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and isinstance(row.get("name"), str):
            result[row["name"]] = row.get("value")
    return result


def validate(document: dict) -> dict:
    workflow = workflow_root(document)
    draft = load_json(HERE / "draft_workflow.json")
    catalog = load_json(HERE / "node_catalog.json")["nodes"]
    expected_names = [node["name"] for node in draft["nodes"]]
    expected_by_name = by_name(draft)
    nodes = by_name(workflow)
    errors: list[dict] = []
    warnings: list[dict] = []

    def error(code: str, node: str | None, message: str) -> None:
        errors.append({"code": code, "node": node, "message": message})

    if workflow.get("active") is not False:
        error("release_state", None, "workflow must remain inactive until credentials are bound")
    if set(nodes) != set(expected_names) or len(workflow.get("nodes", [])) != len(expected_names):
        error("node_set", None, "node names must exactly match the draft export")
    if workflow.get("connections") != draft.get("connections"):
        error("connections", None, "connection graph differs from the draft")

    uuid4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)
    seen_ids = set()
    for name, current in nodes.items():
        original = expected_by_name.get(name, {})
        for field in ("id", "name", "type", "position"):
            if current.get(field) != original.get(field):
                error("identity", name, f"{field} differs from the draft")
        node_id = current.get("id")
        if not isinstance(node_id, str) or not uuid4.fullmatch(node_id) or node_id in seen_ids:
            error("node_id", name, "node id must be a unique UUID v4")
        seen_ids.add(node_id)
        expected_version = catalog.get(current.get("type"), {}).get("typeVersion")
        if current.get("typeVersion") != expected_version:
            error("type_version", name, f"typeVersion must be {expected_version}")
        if "credentials" in current or "credentials" in current.get("parameters", {}):
            error("credential_binding", name, "credential bindings must be omitted because no ID was supplied")

    def params(name: str) -> dict:
        value = nodes.get(name, {}).get("parameters", {})
        return value if isinstance(value, dict) else {}

    webhook = params("Participant Intake")
    if webhook.get("path") != "research-participant-intake" or webhook.get("httpMethod") != "POST" or webhook.get("responseMode") != "responseNode":
        error("webhook_config", "Participant Intake", "expected POST path and explicit responseNode mode")

    condition_rows = params("Email Present?").get("conditions", {}).get("string", [])
    condition = condition_rows[0] if isinstance(condition_rows, list) and len(condition_rows) == 1 and isinstance(condition_rows[0], dict) else {}
    if condition.get("operation") != "isNotEmpty" or condition.get("singleValue") is not True or "value2" in condition or "body.email" not in str(condition.get("value1", "")):
        error("if_dependency", "Email Present?", "isNotEmpty is unary, needs body.email and singleValue=true, and must not contain value2")

    fetch = params("Fetch Study Metadata")
    query_rows = fetch.get("queryParameters", {}).get("parameters", [])
    query_ok = any(isinstance(row, dict) and row.get("name") == "study_id" and "body.study_id" in str(row.get("value", "")) for row in query_rows) if isinstance(query_rows, list) else False
    if fetch.get("method") != "GET" or fetch.get("sendQuery") is not True or not query_ok or "sendBody" in fetch or "body" in fetch:
        error("http_get_dependency", "Fetch Study Metadata", "GET must send study_id as a query parameter and must not carry body fields")

    check = params("Check Eligibility")
    content = check.get("body", {}).get("content", {})
    needed = {"participant_id", "study_id", "email", "consent"}
    if check.get("method") != "POST" or check.get("sendBody") is not True or check.get("body", {}).get("contentType") != "json" or not isinstance(content, dict) or not needed.issubset(content):
        error("http_post_dependency", "Check Eligibility", "POST must enable a JSON body with the four requested fields")
    elif any(f"body.{key}" not in str(content.get(key, "")) for key in needed):
        error("http_post_mapping", "Check Eligibility", "JSON body fields must map from the webhook body")
    if check.get("authentication") != "predefinedCredentialType" or check.get("nodeCredentialType") != "httpHeaderAuth":
        error("http_auth_type", "Check Eligibility", "named header-auth type is not configured")

    save_node = nodes.get("Save Enrollment", {})
    save = params("Save Enrollment")
    query = str(save.get("query", ""))
    replacements = save.get("options", {}).get("queryReplacement")
    if save.get("operation") != "executeQuery" or any(token not in query for token in ("$1", "$2", "$3", "$4", "ON CONFLICT")) or "{{" in query:
        error("sql_binding", "Save Enrollment", "query must be an INSERT/UPSERT with four placeholders and no expression interpolation")
    if not isinstance(replacements, str) or any(name not in replacements for name in ("participant_id", "study_id", "email", "decision")):
        error("sql_replacements", "Save Enrollment", "queryReplacement must bind the four dynamic values")
    if save.get("options", {}).get("queryBatching") != "transaction":
        error("sql_transaction", "Save Enrollment", "queryBatching must be transaction")
    if save_node.get("alwaysOutputData") is not True:
        error("downstream_continuity", "Save Enrollment", "alwaysOutputData must be enabled at node level")

    switch = params("Route Decision")
    rules = switch.get("rules", {}).get("values", [])
    values = []
    if isinstance(rules, list):
        for rule in rules:
            rows = rule.get("conditions", {}).get("string", []) if isinstance(rule, dict) else []
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                if "Check Eligibility" not in str(rows[0].get("value1", "")):
                    error("switch_source", "Route Decision", "rules must read the eligibility decision explicitly after the database node")
                values.append(rows[0].get("value2"))
    options = switch.get("options", {})
    if set(values) != {"approved", "waitlist"} or options.get("fallbackOutput") != "extra" or not options.get("renameFallbackOutput"):
        error("switch_routes", "Route Decision", "approved/waitlist rules and a named extra fallback are required")

    expected_assignments = {
        "Build Approved Response": {"status", "participant_id"},
        "Build Waitlist Response": {"status", "participant_id"},
        "Build Invalid Response": {"status", "error"},
        "Build Unexpected Response": {"status", "error", "blocks"},
    }
    for name, expected in expected_assignments.items():
        if not expected.issubset(configured_assignments(nodes.get(name, {}))):
            error("response_fields", name, f"response builder is missing one of {sorted(expected)}")

    codes = {"Respond Approved": 201, "Respond Waitlisted": 202, "Respond Invalid": 422, "Respond Unexpected": 500}
    for name, code in codes.items():
        response = params(name)
        if response.get("respondWith") != "json" or response.get("options", {}).get("responseCode") != code:
            error("response_code", name, f"JSON response must explicitly use HTTP {code}")
        body = str(response.get("responseBody", ""))
        if "JSON.stringify" in body or not body.strip():
            error("response_body", name, "responseBody must pass a non-empty object directly, not stringify it")

    slack = params("Notify Coordinator")
    if slack.get("resource") != "message" or slack.get("operation") != "post" or slack.get("channel") != "#research-alerts" or not slack.get("text"):
        error("slack_operation", "Notify Coordinator", "Slack must post a message to #research-alerts")
    raw_blocks = slack.get("blocks")
    blocks = str(raw_blocks)
    if not ((isinstance(raw_blocks, dict) and "blocks" in raw_blocks) or '"blocks"' in blocks or "'blocks'" in blocks):
        error("slack_blocks", "Notify Coordinator", "Block Kit expression must yield an object with a blocks key")

    return {"valid": not errors, "errors": errors, "warnings": warnings, "node_count": len(nodes)}


def command_get_node(args: argparse.Namespace) -> int:
    catalog = load_json(HERE / "node_catalog.json")["nodes"]
    entry = catalog.get(args.node_type)
    if entry is None:
        print(json.dumps({"error": "unknown node type", "nodeType": args.node_type}, indent=2))
        return 2
    if args.search:
        result = {"nodeType": args.node_type, "mode": "search_properties", "query": args.search, "matches": deep_search(entry, args.search.lower())}
    elif args.detail == "full":
        result = {"nodeType": args.node_type, "detail": "full", "schema": entry}
    else:
        result = {
            "nodeType": args.node_type,
            "detail": "standard",
            "typeVersion": entry.get("typeVersion"),
            "required": entry.get("required", entry.get("required_by_operation", [])),
            "operations": entry.get("operations", entry.get("operation_values", entry.get("required_by_operation", {}))),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    try:
        result = validate(load_json(Path(args.workflow)))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"valid": False, "errors": [{"code": "unreadable", "node": None, "message": str(exc)}], "warnings": []}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("valid") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    get_node = sub.add_parser("get_node")
    get_node.add_argument("node_type")
    get_node.add_argument("--detail", choices=("standard", "full"), default="standard")
    get_node.add_argument("--search")
    get_node.set_defaults(func=command_get_node)
    validate_parser = sub.add_parser("validate_workflow")
    validate_parser.add_argument("workflow")
    validate_parser.set_defaults(func=command_validate)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
