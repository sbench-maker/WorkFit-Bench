from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT_PATH = RESULTS_DIR / "rg-helio-prod-architecture.md"


def load_json(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def load_text() -> str:
    assert OUTPUT_PATH.is_file(), "rg-helio-prod-architecture.md is missing, so the requested handoff cannot be used"
    try:
        return OUTPUT_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        pytest.fail(f"the architecture Markdown is not readable UTF-8 text: {exc}")


def load_text_optional() -> str:
    """Keep one missing or unreadable artifact defect from becoming record-level cascades."""
    if not OUTPUT_PATH.is_file():
        return ""
    try:
        return OUTPUT_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def mermaid_blocks(text: str) -> list[str]:
    return re.findall(r"```\s*mermaid\s*\n(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)


def prose_without_mermaid(text: str) -> str:
    return re.sub(r"```\s*mermaid\s*\n.*?```", "", text, flags=re.IGNORECASE | re.DOTALL)


def all_entities() -> tuple[list[dict], list[dict]]:
    return load_json("resources.json"), load_json("external_resources.json")


NODE_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*(?:\[\[?|\(\(?|\{\{?)\s*[\"']?(.*?)[\"']?\s*(?:\]\]?|\)\)?|\}\}?)\s*;?\s*(?:::[A-Za-z_][A-Za-z0-9_-]*)?\s*$"
)
EDGE_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*(==>|-->|-\.->)\s*(?:\|\s*[\"']?(.*?)[\"']?\s*\|\s*)?([A-Za-z_][A-Za-z0-9_-]*)",
)
TEXT_EDGE_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*--\s*[\"']?(.*?)[\"']?\s*-->\s*([A-Za-z_][A-Za-z0-9_-]*)"
)


def parse_mermaid(text: str) -> tuple[dict[str, str], list[dict]]:
    resources, externals = all_entities()
    entities = resources + externals
    names = sorted(((row["name"], row["resource_id"]) for row in entities), key=lambda item: len(item[0]), reverse=True)
    node_to_resource: dict[str, str] = {}
    raw_edges: list[tuple[str, str, str]] = []
    for block in mermaid_blocks(text):
        for raw_line in block.splitlines():
            line = raw_line.strip()
            node_match = NODE_RE.match(line)
            if node_match and not line.lower().startswith(("graph ", "flowchart ", "subgraph ")):
                node_id, label = node_match.groups()
                label_norm = norm(label)
                for name, resource_id in names:
                    if norm(name) in label_norm:
                        node_to_resource[node_id] = resource_id
                        break
            edge_match = EDGE_RE.match(line)
            if edge_match:
                source, _, label, target = edge_match.groups()
                raw_edges.append((source, target, (label or "").strip(" \"'")))
                continue
            text_edge_match = TEXT_EDGE_RE.match(line)
            if text_edge_match:
                source, label, target = text_edge_match.groups()
                raw_edges.append((source, target, label.strip(" \"'")))

    edges = []
    for source_node, target_node, label in raw_edges:
        if source_node in node_to_resource and target_node in node_to_resource:
            edges.append(
                {
                    "source": node_to_resource[source_node],
                    "target": node_to_resource[target_node],
                    "label": label,
                }
            )
    return node_to_resource, edges


def expected_edges() -> dict[str, list[dict]]:
    resources, externals = all_entities()
    valid_ids = {row["resource_id"] for row in resources + externals}
    external_ids = {row["resource_id"] for row in externals}
    expected: dict[str, list[dict]] = defaultdict(list)
    seen: set[tuple[str, str, str, str]] = set()

    def add(category: str, source: str, target: str, label: str, tokens: set[str]) -> None:
        if source not in valid_ids or target not in valid_ids:
            return
        marker = (category, source, target, norm(label))
        if marker in seen:
            return
        seen.add(marker)
        expected[category].append(
            {"source": source, "target": target, "label": label, "tokens": {norm(token) for token in tokens if norm(token)}}
        )

    stopwords = {"and", "with", "over", "into", "from", "only", "current"}
    for flow in load_json("verified_flows.json"):
        if flow.get("status") != "verified" or flow.get("active") is not True:
            continue
        source, target = flow["source_id"], flow["target_id"]
        if source in external_ids or target in external_ids:
            category = "external_dependencies"
        elif any(word in flow["relation"].lower() for word in ("telemetry", "monitor", "alert", "security log")):
            category = "observability"
        else:
            category = "runtime_data_flows"
        words = re.findall(r"[A-Za-z0-9]+", f'{flow["relation"]} {flow["protocol"]}')
        tokens = {word for word in words if len(word) >= 3 and word.lower() not in stopwords}
        add(category, source, target, flow["relation"], tokens)

    link_rules = {
        "waf_policy_id": ("hosting_dependencies", "resource_to_value", "WAF policy", {"waf", "policy", "protect"}),
        "frontend_ip_id": ("network_placement", "value_to_resource", "frontend IP", {"front", "frontend", "ip"}),
        "parent_vnet_id": ("network_placement", "value_to_resource", "contains subnet", {"contain", "subnet", "vnet", "network"}),
        "nsg_id": ("network_placement", "value_to_resource", "NSG protects", {"nsg", "protect", "security", "filter"}),
        "route_table_id": ("network_placement", "value_to_resource", "routes subnet", {"route", "routes", "routing"}),
        "subnet_id": ("network_placement", "value_to_resource", "subnet placement", {"host", "subnet", "integrat", "placement", "private"}),
        "plan_id": ("hosting_dependencies", "value_to_resource", "plan hosts workload", {"host", "plan", "compute"}),
        "environment_id": ("hosting_dependencies", "value_to_resource", "environment hosts app", {"host", "environment", "container"}),
        "parent_server_id": ("hosting_dependencies", "value_to_resource", "server hosts database", {"host", "server", "database", "parent"}),
        "parent_namespace_id": ("hosting_dependencies", "value_to_resource", "namespace contains queue", {"contain", "namespace", "queue", "parent"}),
        "target_resource_id": ("network_placement", "resource_to_value", "private link", {"private", "link", "endpoint"}),
        "dns_zone_id": ("network_placement", "value_to_resource", "private DNS resolution", {"dns", "resolve", "private"}),
        "linked_vnet_id": ("network_placement", "value_to_resource", "VNet DNS link", {"dns", "vnet", "link"}),
        "managed_identity_id": ("identity_access", "resource_to_value", "uses managed identity", {"identity", "managed", "principal"}),
        "app_insights_id": ("observability", "resource_to_value", "emits telemetry", {"telemetry", "insight", "monitor"}),
        "workspace_id": ("observability", "resource_to_value", "stores telemetry", {"telemetry", "workspace", "logs", "store"}),
        "diagnostic_workspace_id": ("observability", "resource_to_value", "sends diagnostics", {"diagnostic", "logs", "workspace", "monitor"}),
        "monitored_resource_id": ("observability", "resource_to_value", "monitors latency", {"monitor", "latency", "metric"}),
        "action_group_id": ("observability", "resource_to_value", "alert notification", {"alert", "notify", "notification", "action"}),
    }
    for item in load_json("resource_properties.json"):
        key = item["property"]
        if key not in link_rules or ";" in str(item["value"]):
            continue
        category, direction, label, tokens = link_rules[key]
        if direction == "resource_to_value":
            source, target = item["resource_id"], str(item["value"])
        else:
            source, target = str(item["value"]), item["resource_id"]
        add(category, source, target, label, tokens)

    for assignment in load_json("role_assignments.json"):
        if assignment.get("active") is not True:
            continue
        role_words = {word for word in re.findall(r"[A-Za-z0-9]+", assignment["role"]) if len(word) >= 4}
        add(
            "identity_access",
            assignment["principal_resource_id"],
            assignment["scope_resource_id"],
            assignment["role"],
            role_words | {"role", "access"},
        )
    return expected


def label_matches(actual: str, tokens: set[str]) -> bool:
    actual_norm = norm(actual)
    return bool(actual_norm) and any(token in actual_norm for token in tokens)


@pytest.mark.parametrize("surface", ["document", "diagram", "external_boundary"])
def test_resource_scope(surface: str):
    """Criterion: resource_scope."""
    text = load_text_optional()
    if not text:
        pytest.fail("resource scope cannot be checked because the requested Markdown is unavailable")
    resources, externals = all_entities()
    blocks = mermaid_blocks(text)
    diagram = "\n".join(blocks)
    prose = prose_without_mermaid(text)
    if surface == "document":
        missing = [row["name"] for row in resources if norm(row["name"]) not in norm(prose)]
        assert not missing, f"in-group resources are missing from the written inventory/accounting: {missing}"
        context = load_json("resource_group.json")
        assert norm(context["resource_group"]) in norm(text), "the resource-group name is missing"
        assert norm(context["subscription_name"]) in norm(text), "the subscription name is missing"
        assert norm(context["primary_region"]) in norm(text), "the primary region is missing"
        assert re.search(r"(?:resource\s*count|resources?)\D{0,18}40\b|\b40\D{0,18}(?:in[- ]group\s+)?resources?", text, flags=re.IGNORECASE), (
            "the document does not make the 40-resource in-group scope clear"
        )
    elif surface == "diagram":
        missing = [row["name"] for row in resources if norm(row["name"]) not in norm(diagram)]
        assert not missing, f"in-group resources are missing from the Mermaid topology: {missing}"
    else:
        missing = [row["name"] for row in externals if norm(row["name"]) not in norm(diagram)]
        assert not missing, f"documented external dependency nodes are missing from the Mermaid topology: {missing}"
        external_markers = ["external", "outside", "crossgroup", "shared"]
        assert any(marker in norm(diagram) for marker in external_markers), (
            "the Mermaid source does not visibly identify the cross-group dependency boundary"
        )
        for group in {row["resource_group"] for row in externals}:
            assert norm(group) in norm(diagram), f"external resource-group context {group} is not shown"


@pytest.mark.parametrize(
    "category",
    [
        "network_placement",
        "hosting_dependencies",
        "runtime_data_flows",
        "identity_access",
        "observability",
        "external_dependencies",
    ],
)
def test_relationship_category_coverage(category: str):
    """Criterion: topology_correctness."""
    text = load_text_optional()
    if not text:
        pytest.fail("relationship topology cannot be checked because the requested Markdown is unavailable")
    _, actual_edges = parse_mermaid(text)
    expected = expected_edges()[category]
    matched = 0
    missing_examples = []
    for edge in expected:
        candidates = [
            row for row in actual_edges
            if row["source"] == edge["source"] and row["target"] == edge["target"]
        ]
        if any(label_matches(row["label"], edge["tokens"]) for row in candidates):
            matched += 1
        elif len(missing_examples) < 6:
            missing_examples.append(f'{edge["source"]}->{edge["target"]} ({edge["label"]})')
    required_ratio = 0.90 if len(expected) >= 10 else 1.0
    ratio = matched / len(expected) if expected else 1.0
    assert ratio >= required_ratio, (
        f"{category} maps only {matched}/{len(expected)} expected relationships with meaningful labels; "
        f"examples missing or mislabeled: {missing_examples}"
    )


def test_unconfirmed_connections_are_not_drawn():
    """Criterion: topology_correctness."""
    text = load_text_optional()
    if not text:
        pytest.fail("candidate-link handling cannot be checked because the requested Markdown is unavailable")
    _, edges = parse_mermaid(text)
    actual_pairs = {(row["source"], row["target"]) for row in edges}
    candidate_pairs = {
        (row["source_id"], row["target_id"])
        for row in load_json("verified_flows.json")
        if row.get("status") != "verified" or row.get("active") is not True
    }
    inactive_pairs = {
        (row["principal_resource_id"], row["scope_resource_id"])
        for row in load_json("role_assignments.json")
        if row.get("active") is not True
    }
    asserted = sorted(actual_pairs & (candidate_pairs | inactive_pairs))
    assert not asserted, f"candidate-only or inactive connections are drawn as current topology: {asserted}"


def lines_near_name(text: str, name: str, radius: int = 1) -> str:
    lines = text.splitlines()
    selected = []
    target = norm(name)
    for index, line in enumerate(lines):
        if target in norm(line):
            selected.extend(lines[max(0, index - radius): min(len(lines), index + radius + 1)])
    return "\n".join(selected)


CONFIG_CASES = {
    "inventory_facts": [],
    "network_and_edge": [
        ("vnet-helio-prod", "10.42.0.0/16"),
        ("snet-edge", "10.42.1.0/24"),
        ("snet-app", "10.42.2.0/24"),
        ("snet-data", "10.42.3.0/24"),
        ("appgw-helio-prod", "2-10"),
        ("appgw-helio-prod", "disabled"),
        ("waf-helio-prod", "Prevention"),
    ],
    "compute": [
        ("app-web-helio-prod", "Node.js 20 LTS"),
        ("app-api-helio-prod", ".NET 8"),
        ("func-orders-helio-prod", "Python 3.11"),
        ("func-events-helio-prod", "Node.js 20 LTS"),
        ("ca-search-indexer-helio-prod", "1"),
        ("ca-search-indexer-helio-prod", "6"),
    ],
    "data_and_security": [
        ("sqldb-orders-helio-prod", "Local"),
        ("sqldb-orders-helio-prod", "false"),
        ("cosmos-catalog-helio-prod", "Serverless"),
        ("sthelioprod", "Standard_ZRS"),
        ("sb-helio-prod", "Premium"),
        ("redis-helio-prod", "Premium_P1"),
        ("kv-helio-prod", "90"),
        ("pe-sql-helio-prod", "Approved"),
    ],
    "observability": [
        ("log-helio-prod", "90"),
        ("appi-web-helio-prod", "10"),
        ("appi-api-helio-prod", "20"),
        ("ag-ops-helio-prod", "1"),
        ("alert-api-latency-helio-prod", "2 seconds for 10 minutes"),
    ],
    "credential_safety": [],
}


@pytest.mark.parametrize("case", list(CONFIG_CASES))
def test_configuration_accuracy(case: str):
    """Criterion: configuration_accuracy."""
    text = load_text_optional()
    if not text:
        pytest.fail("configuration accuracy cannot be checked because the requested Markdown is unavailable")
    resources = load_json("resources.json")
    if case == "inventory_facts":
        problems = []
        for row in resources:
            nearby = norm(lines_near_name(text, row["name"], radius=0))
            if norm(row["location"]) not in nearby:
                problems.append(f'{row["name"]}: location {row["location"]}')
            if row["sku"] != "Not applicable" and norm(row["sku"]) not in nearby:
                problems.append(f'{row["name"]}: SKU {row["sku"]}')
        assert not problems, "resource facts are missing or associated with the wrong resource line: " + "; ".join(problems[:12])
        return
    if case == "credential_safety":
        dangerous_patterns = [
            r"AccountKey\s*=\s*[^;\s<]{8,}",
            r"SharedAccessSignature\s*=\s*[^;\s<]{8,}",
            r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----",
            r"(?:client[_ -]?secret|password)\s*[:=]\s*(?!<redacted>|redacted|not collected|placeholder)[\"']?[^\s,;\"']{8,}",
        ]
        matches = [pattern for pattern in dangerous_patterns if re.search(pattern, text, flags=re.IGNORECASE)]
        assert not matches, "the document appears to contain a fabricated or exposed credential value"
        return
    problems = []
    for resource_name, expected_value in CONFIG_CASES[case]:
        nearby = lines_near_name(text, resource_name, radius=1)
        if norm(expected_value) not in norm(nearby):
            problems.append(f"{resource_name} should show {expected_value}")
    assert not problems, "architecture-relevant configuration is missing or misassociated: " + "; ".join(problems)
