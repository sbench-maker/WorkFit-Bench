from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("TASK_OUTPUT_PATH", "/root/results/configured_workflow.json"))


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_workflow() -> tuple[dict | None, str | None]:
    if not OUTPUT.is_file():
        return None, "configured_workflow.json is missing"
    try:
        document = read_json(OUTPUT)
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"configured_workflow.json is unreadable: {exc}"
    if not isinstance(document, dict):
        return None, "configured_workflow.json must contain a JSON object"
    workflow = document
    if not isinstance(workflow.get("nodes"), list) or not isinstance(workflow.get("connections"), dict):
        return None, "the workflow export must expose nodes and connections"
    return workflow, None


def usable_workflow() -> dict:
    workflow, issue = normalize_workflow()
    assert workflow is not None, issue
    return workflow


def nodes_by_name(workflow: dict) -> dict[str, dict]:
    result = {}
    for row in workflow.get("nodes", []):
        if isinstance(row, dict) and isinstance(row.get("name"), str):
            result[row["name"]] = row
    return result


def parameters(nodes: dict[str, dict], name: str) -> dict:
    value = nodes.get(name, {}).get("parameters")
    assert isinstance(value, dict), f"{name} has no usable parameters object"
    return value


def assignment_map(node: dict) -> dict[str, object]:
    params = node.get("parameters", {})
    container = params.get("assignments", {}) if isinstance(params, dict) else {}
    rows = container.get("assignments", []) if isinstance(container, dict) else []
    result = {}
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and isinstance(row.get("name"), str):
            result[row["name"]] = row.get("value")
    return result


def test_export_preserves_workflow_contract():
    workflow = usable_workflow()
    draft = read_json(DATA / "draft_workflow.json")
    assert workflow.get("id") == draft["id"] and workflow.get("name") == draft["name"], (
        "the deployable export must retain the workflow identity from the draft"
    )
    assert workflow.get("active") is False, "the workflow must remain inactive for credential review"
    expected = {node["name"]: node for node in draft["nodes"]}
    actual = nodes_by_name(workflow)
    assert len(workflow["nodes"]) == len(expected) and set(actual) == set(expected), (
        "all and only the existing draft nodes must remain in the export"
    )
    for name, original in expected.items():
        for field in ("id", "name", "type", "position"):
            assert actual[name].get(field) == original.get(field), f"{name} changed its preserved {field}"
    assert workflow["connections"] == draft["connections"], (
        "the supplied wiring changed, so a documented response path may no longer execute"
    )


@pytest.mark.parametrize("case", ["versions", "webhook_if", "http_get", "http_post", "response_builders"])
def test_operation_specific_and_conditional_configuration(case: str):
    workflow = usable_workflow()
    nodes = nodes_by_name(workflow)
    catalog = read_json(DATA / "node_catalog.json")["nodes"]

    if case == "versions":
        uuid4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)
        ids = [node.get("id") for node in nodes.values()]
        assert len(ids) == len(set(ids)) and all(isinstance(value, str) and uuid4.fullmatch(value) for value in ids), (
            "node identities are not unique UUID v4 values"
        )
        for name, node in nodes.items():
            assert node.get("typeVersion") == catalog[node["type"]]["typeVersion"], (
                f"{name} does not use the bundled catalog version"
            )
    elif case == "webhook_if":
        webhook = parameters(nodes, "Participant Intake")
        assert (webhook.get("path"), webhook.get("httpMethod"), webhook.get("responseMode")) == (
            "research-participant-intake", "POST", "responseNode"
        ), "Participant Intake does not wait for the configured response branches"
        rows = parameters(nodes, "Email Present?").get("conditions", {}).get("string", [])
        assert isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], dict)
        condition = rows[0]
        assert condition.get("operation") == "isNotEmpty" and condition.get("singleValue") is True, (
            "Email Present? must use the unary non-empty operator shape"
        )
        assert "value2" not in condition and "body.email" in str(condition.get("value1", "")), (
            "Email Present? carries a hidden binary operand or reads outside the webhook body"
        )
    elif case == "http_get":
        get = parameters(nodes, "Fetch Study Metadata")
        rows = get.get("queryParameters", {}).get("parameters", [])
        assert get.get("method") == "GET" and get.get("sendQuery") is True
        assert "sendBody" not in get and "body" not in get, "the GET node retains method-inapplicable body fields"
        assert isinstance(rows, list) and any(
            isinstance(row, dict) and row.get("name") == "study_id" and "body.study_id" in str(row.get("value", ""))
            for row in rows
        ), "the study lookup does not send the webhook study_id as a query parameter"
    elif case == "http_post":
        post = parameters(nodes, "Check Eligibility")
        content = post.get("body", {}).get("content", {})
        required = {"participant_id", "study_id", "email", "consent"}
        assert post.get("method") == "POST" and post.get("sendBody") is True
        assert post.get("body", {}).get("contentType") == "json" and isinstance(content, dict) and required.issubset(content)
        assert all(f"body.{field}" in str(content[field]) for field in required), (
            "eligibility JSON fields are not all sourced from the webhook body"
        )
        assert post.get("authentication") == "predefinedCredentialType" and post.get("nodeCredentialType") == "httpHeaderAuth"
    else:
        expected = {
            "Build Approved Response": {"status": "approved", "participant_id": None},
            "Build Waitlist Response": {"status": "waitlist", "participant_id": None},
            "Build Invalid Response": {"status": "invalid", "error": "missing_email"},
            "Build Unexpected Response": {"status": "error", "error": "unexpected_decision", "blocks": None},
        }
        for name, fields in expected.items():
            actual = assignment_map(nodes.get(name, {}))
            assert set(fields).issubset(actual), f"{name} does not build all requested response fields"
            for field, fixed in fields.items():
                if fixed is not None:
                    assert actual[field] == fixed, f"{name}.{field} changes the response meaning"
            if "participant_id" in fields:
                assert "body.participant_id" in str(actual["participant_id"]), f"{name} loses the participant identifier"
        assert isinstance(assignment_map(nodes["Build Unexpected Response"])["blocks"], (str, list)), (
            "the unexpected response does not expose Block Kit content for the alert"
        )


@pytest.mark.parametrize("case", ["credentials_release", "sql_binding", "transaction_continuity"])
def test_database_security_and_review_readiness(case: str):
    workflow = usable_workflow()
    nodes = nodes_by_name(workflow)
    save_node = nodes.get("Save Enrollment", {})
    save = parameters(nodes, "Save Enrollment")

    if case == "credentials_release":
        def has_credentials(value: object) -> bool:
            if isinstance(value, dict):
                return any(str(key).lower() == "credentials" or has_credentials(child) for key, child in value.items())
            if isinstance(value, list):
                return any(has_credentials(child) for child in value)
            return False

        assert workflow.get("active") is False, "unbound integrations must not be activated"
        assert not has_credentials(workflow), "the export contains a placeholder or invented credential binding"
    elif case == "sql_binding":
        query = str(save.get("query", ""))
        assert save.get("operation") == "executeQuery" and "INSERT INTO enrollments" in query and "ON CONFLICT" in query.upper()
        assert all(f"${index}" in query for index in range(1, 5)), "the UPSERT is missing one or more bound placeholders"
        assert "{{" not in query and "}}" not in query, "dynamic input is interpolated into SQL text"
        replacements = save.get("options", {}).get("queryReplacement")
        assert isinstance(replacements, str) and all(field in replacements for field in ("participant_id", "study_id", "email", "decision")), (
            "queryReplacement does not bind all four dynamic values"
        )
    else:
        assert save.get("options", {}).get("queryBatching") == "transaction", (
            "the enrollment UPSERT is not explicitly atomic"
        )
        assert save_node.get("alwaysOutputData") is True, (
            "a zero-row database result can stop decision routing downstream"
        )


@pytest.mark.parametrize("case", ["switch", "response_codes", "slack_alert", "sample_path_coverage"])
def test_routing_and_response_behavior(case: str):
    workflow = usable_workflow()
    nodes = nodes_by_name(workflow)

    if case == "switch":
        switch = parameters(nodes, "Route Decision")
        rules = switch.get("rules", {}).get("values", [])
        assert isinstance(rules, list) and len(rules) == 2
        decisions = set()
        names = []
        for rule in rules:
            rows = rule.get("conditions", {}).get("string", []) if isinstance(rule, dict) else []
            assert len(rows) == 1 and rows[0].get("operation") == "equals"
            assert "decision" in str(rows[0].get("value1", "")) and "Check Eligibility" in str(rows[0].get("value1", "")), (
                "decision routing reads the possibly empty database output instead of the eligibility result"
            )
            decisions.add(rows[0].get("value2"))
            if rule.get("renameOutput") is True and rule.get("outputKey"):
                names.append(str(rule["outputKey"]).strip())
        assert decisions == {"approved", "waitlist"} and len(names) == 2 and all(names) and len(set(names)) == 2
        options = switch.get("options", {})
        assert options.get("fallbackOutput") == "extra" and str(options.get("renameFallbackOutput", "")).strip(), (
            "unmatched decisions would be dropped or the fallback is not identifiable"
        )
    elif case == "response_codes":
        expected = {"Respond Approved": 201, "Respond Waitlisted": 202, "Respond Invalid": 422, "Respond Unexpected": 500}
        for name, code in expected.items():
            response = parameters(nodes, name)
            assert response.get("respondWith") == "json" and response.get("options", {}).get("responseCode") == code, (
                f"{name} does not explicitly return HTTP {code} as JSON"
            )
            body = str(response.get("responseBody", ""))
            assert body.strip() and "JSON.stringify" not in body, f"{name} double-encodes or loses the response object"
    elif case == "slack_alert":
        slack = parameters(nodes, "Notify Coordinator")
        assert (slack.get("resource"), slack.get("operation"), slack.get("channel")) == ("message", "post", "#research-alerts")
        assert str(slack.get("text", "")).strip(), "the coordinator alert has no fallback text"
        raw_blocks = slack.get("blocks")
        blocks = str(raw_blocks)
        wrapped = (isinstance(raw_blocks, dict) and "blocks" in raw_blocks) or "'blocks'" in blocks or '"blocks"' in blocks
        sourced = isinstance(raw_blocks, dict) or "Build Unexpected Response" in blocks
        assert wrapped and sourced, (
            "the alert does not pass the built Block Kit array inside a blocks object"
        )
    else:
        paths = {
            json.loads(line)["expected_response_path"]
            for line in (DATA / "sample_submissions.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        assert paths == {"approved", "waitlist", "invalid", "unexpected"}
        required_nodes = {
            "approved": ("Build Approved Response", "Respond Approved"),
            "waitlist": ("Build Waitlist Response", "Respond Waitlisted"),
            "invalid": ("Build Invalid Response", "Respond Invalid"),
            "unexpected": ("Build Unexpected Response", "Respond Unexpected"),
        }
        assert all(all(name in nodes for name in required_nodes[path]) for path in paths), (
            "the export lacks a response builder or responder for a path present in the supplied examples"
        )
