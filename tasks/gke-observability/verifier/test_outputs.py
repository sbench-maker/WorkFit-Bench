from __future__ import annotations

import json
import os
import re
import shlex
from pathlib import Path

import pytest


OUTPUT = Path(os.environ.get("TASK_OUTPUT_PATH", "/root/results/observability_rollout.json"))
DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))

MONITOR_TO_API = {"SYSTEM": "SYSTEM_COMPONENTS", "API_SERVER": "APISERVER"}
LOGGING_TO_API = {"SYSTEM": "SYSTEM_COMPONENTS", "WORKLOAD": "WORKLOADS"}


def load_inputs() -> tuple[list[dict], dict]:
    clusters = json.loads((DATA / "clusters.json").read_text(encoding="utf-8"))
    policy = json.loads((DATA / "fleet_policy.json").read_text(encoding="utf-8"))
    return clusters, policy


CLUSTERS, POLICY = load_inputs()
CLUSTER_BY_NAME = {row["cluster_name"]: row for row in CLUSTERS}
PRODUCTION_NAMES = {row["cluster_name"] for row in CLUSTERS if row["environment"] == "production"}


def desired_state(cluster: dict) -> dict:
    profile = POLICY["profiles"][cluster["environment"]]
    monitoring = list(profile["monitoring_components"])
    if cluster["environment"] == "staging" and cluster["gpu_nodes"]:
        monitoring.append("DCGM")
    if cluster["environment"] == "production":
        prometheus = True
        dataplane = cluster["dataplane_v2"]
    elif cluster["environment"] == "staging":
        prometheus = cluster["custom_metrics_required"]
        dataplane = cluster["dataplane_v2"]
    else:
        prometheus = False
        dataplane = False
    return {
        "logging_components": set(profile["logging_components"]),
        "monitoring_components": set(monitoring),
        "managed_prometheus_enabled": prometheus,
        "dataplane_v2_metrics_enabled": dataplane,
        "logging_service": POLICY["service_endpoints"]["logging_service"],
        "monitoring_service": POLICY["service_endpoints"]["monitoring_service"],
    }


EXPECTED = {name: desired_state(cluster) for name, cluster in CLUSTER_BY_NAME.items()}


def current_normalized(cluster: dict) -> dict:
    state = dict(cluster["current_observability"])
    state["logging_components"] = set(state["logging_components"])
    state["monitoring_components"] = set(state["monitoring_components"])
    return state


def has_drift(cluster: dict) -> bool:
    return current_normalized(cluster) != EXPECTED[cluster["cluster_name"]]


def norm_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def text(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(str(key) + " " + text(item) for key, item in value.items())
    if isinstance(value, list):
        return " ".join(text(item) for item in value)
    return "" if value is None else str(value)


def normalized_text(value: object) -> str:
    return re.sub(r"\s+", " ", text(value).lower().replace("_", " ")).strip()


def load_submission_or_skip() -> object:
    if not OUTPUT.is_file():
        pytest.skip("artifact usability test reports the missing submission")
    try:
        value = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pytest.skip("artifact usability test reports the unreadable submission")
    if not isinstance(value, (dict, list)) or not value:
        pytest.skip("artifact usability test reports the empty submission")
    return value


def walk_dicts(value: object, path: tuple[str, ...] = ()):  # noqa: ANN202
    if isinstance(value, dict):
        yield value, path
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                yield from walk_dicts(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (dict, list)):
                yield from walk_dicts(child, path + (str(index),))


def cluster_records(report: object) -> tuple[dict[str, dict], dict[str, int]]:
    candidates: dict[str, list[tuple[int, dict]]] = {name: [] for name in CLUSTER_BY_NAME}
    occurrences = {name: 0 for name in CLUSTER_BY_NAME}
    for item, path in walk_dicts(report):
        scalar_values = {str(v) for v in item.values() if not isinstance(v, (dict, list))}
        parent = path[-1] if path else ""
        for name in CLUSTER_BY_NAME:
            direct = name in scalar_values or parent == name
            if not direct:
                continue
            occurrences[name] += 1
            key_text = " ".join(str(key).lower() for key in item)
            score = sum(term in key_text for term in ("target", "desired", "command", "decision", "status", "project", "location"))
            candidate = dict(item)
            candidate.setdefault("cluster_name", name)
            candidates[name].append((score, candidate))
    chosen = {}
    for name, rows in candidates.items():
        if rows:
            chosen[name] = max(rows, key=lambda pair: (pair[0], len(pair[1])))[1]
    return chosen, occurrences


def target_container(record: dict) -> dict:
    preferred = []
    for key, value in record.items():
        if isinstance(value, dict) and any(term in norm_key(key) for term in ("target", "desired", "after", "goal")):
            preferred.append(value)
    return preferred[0] if preferred else record


def keyed_values(value: object, path: tuple[str, ...] = ()):  # noqa: ANN202
    if isinstance(value, dict):
        for key, child in value.items():
            yield path, str(key), child
            if isinstance(child, (dict, list)):
                yield from keyed_values(child, path + (str(key),))
    elif isinstance(value, list):
        for child in value:
            if isinstance(child, (dict, list)):
                yield from keyed_values(child, path)


def component_value(target: dict, kind: str) -> set[str] | None:
    for path, key, value in keyed_values(target):
        key_norm = norm_key(key)
        path_norm = norm_key(" ".join(path))
        direct = kind in key_norm and ("component" in key_norm or key_norm in {kind, f"{kind}config"})
        nested = key_norm in {"components", "enabledcomponents"} and kind in path_norm
        if (direct or nested) and isinstance(value, (list, tuple, set, str)):
            raw = re.split(r"[,\s]+", value) if isinstance(value, str) else list(value)
            aliases = LOGGING_TO_API if kind == "logging" else MONITOR_TO_API
            return {aliases.get(str(item).strip().upper().replace("-", "_"), str(item).strip().upper().replace("-", "_")) for item in raw if str(item).strip()}
    return None


def scalar_value(target: dict, family: str) -> object | None:
    for path, key, value in keyed_values(target):
        key_norm = norm_key(key)
        path_norm = norm_key(" ".join(path))
        if family == "managed_prometheus":
            match = ("managed" in key_norm and "prometheus" in key_norm) or (key_norm in {"enabled", "status"} and "managedprometheus" in path_norm)
        elif family == "dataplane":
            match = ("dataplane" in key_norm and ("metric" in key_norm or "observability" in key_norm)) or (key_norm in {"enabled", "enablemetrics"} and "datapathobservability" in path_norm)
        elif family == "logging_service":
            match = "loggingservice" in key_norm
        else:
            match = "monitoringservice" in key_norm
        if match and not isinstance(value, (dict, list)):
            if family in {"managed_prometheus", "dataplane"}:
                if isinstance(value, bool):
                    return value
                lowered = str(value).strip().lower()
                if lowered in {"true", "enabled", "enable", "yes", "on", "1"}:
                    return True
                if lowered in {"false", "disabled", "disable", "no", "off", "0"}:
                    return False
            return value
    return None


def extract_target(record: dict) -> dict:
    target = target_container(record)
    return {
        "logging_components": component_value(target, "logging"),
        "monitoring_components": component_value(target, "monitoring"),
        "managed_prometheus_enabled": scalar_value(target, "managed_prometheus"),
        "dataplane_v2_metrics_enabled": scalar_value(target, "dataplane"),
        "logging_service": scalar_value(target, "logging_service"),
        "monitoring_service": scalar_value(target, "monitoring_service"),
    }


def apply_commands(record: dict) -> list[str]:
    commands = []

    def visit(value: object, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, path + (str(key),))
        elif isinstance(value, list):
            for child in value:
                visit(child, path)
        elif isinstance(value, str) and "gcloud" in value.lower():
            path_text = " ".join(path).lower()
            if "rollback" not in path_text and any(term in path_text for term in ("command", "apply", "update", "action", "execute")):
                commands.append(value.strip())

    visit(record)
    return list(dict.fromkeys(commands))


def option_values(tokens: list[str], option: str) -> list[str]:
    found = []
    for index, token in enumerate(tokens):
        if token == option and index + 1 < len(tokens):
            found.append(tokens[index + 1])
        elif token.startswith(option + "="):
            found.append(token.split("=", 1)[1])
    return found


def combined_tokens(commands: list[str]) -> list[str]:
    result = []
    for command in commands:
        try:
            result.extend(shlex.split(command))
        except ValueError:
            result.extend(command.split())
    return result


def normalized_flag_components(value: str, aliases: dict[str, str]) -> set[str]:
    return {
        aliases.get(item.strip().upper().replace("-", "_"), item.strip().upper().replace("-", "_"))
        for item in value.split(",")
        if item.strip()
    }


def find_contexts(report: object, required_terms: tuple[str, ...], path_term: str | None = None) -> list[tuple[dict, str]]:
    rows = []
    for item, path in walk_dicts(report):
        context = normalized_text(item)
        if path_term and path_term not in norm_key(" ".join(path)):
            continue
        if all(term.lower() in context for term in required_terms):
            rows.append((item, context))
    return rows


def test_cluster_coverage_and_decisions():
    report = load_submission_or_skip()
    records, _ = cluster_records(report)
    missing = set(CLUSTER_BY_NAME) - set(records)
    assert not missing, f"fleet clusters missing attributable plans: {sorted(missing)}"
    errors = []
    for name, cluster in CLUSTER_BY_NAME.items():
        context = normalized_text(records[name])
        expected_noop = not has_drift(cluster)
        says_noop = any(term in context for term in ("no-op", "no op", "noop", "compliant", "no change"))
        says_change = any(term in context for term in ("change", "update", "remediate", "drift"))
        if expected_noop and not says_noop:
            errors.append(f"{name} is compliant but not explicitly marked no-op")
        if not expected_noop and (not says_change or says_noop):
            errors.append(f"{name} has drift but is not unambiguously marked for change")
    assert not errors, "; ".join(errors)


@pytest.mark.parametrize("environment", ["production", "staging", "sandbox"])
def test_cluster_target_states(environment: str):
    report = load_submission_or_skip()
    records, _ = cluster_records(report)
    if set(CLUSTER_BY_NAME) - set(records):
        pytest.skip("coverage test reports missing cluster records")
    errors = []
    for name, cluster in CLUSTER_BY_NAME.items():
        if cluster["environment"] != environment:
            continue
        actual = extract_target(records[name])
        expected = EXPECTED[name]
        for key, expected_value in expected.items():
            actual_value = actual[key]
            if actual_value != expected_value:
                errors.append(f"{name} {key}={actual_value!r}, expected {expected_value!r}")
    assert not errors, "; ".join(errors)


@pytest.mark.parametrize("environment", ["production", "staging", "sandbox"])
def test_apply_commands_implement_drift(environment: str):
    report = load_submission_or_skip()
    records, _ = cluster_records(report)
    errors = []
    for name, cluster in CLUSTER_BY_NAME.items():
        if cluster["environment"] != environment or not has_drift(cluster) or name not in records:
            continue
        commands = apply_commands(records[name])
        if not commands:
            errors.append(f"{name} has drift but no attributable apply command")
            continue
        tokens = combined_tokens(commands)
        joined = " ".join(tokens)
        if not re.search(rf"\bgcloud\s+container\s+clusters\s+update\s+{re.escape(name)}\b", joined):
            errors.append(f"{name} command does not target that cluster")
        if cluster["project_id"] not in option_values(tokens, "--project"):
            errors.append(f"{name} command omits project {cluster['project_id']}")
        correct_location = cluster["location"] in (
            option_values(tokens, "--location")
            + option_values(tokens, "--region" if cluster["location_type"] == "regional" else "--zone")
        )
        if not correct_location:
            errors.append(f"{name} command does not use its {cluster['location_type']} location {cluster['location']}")

        current = current_normalized(cluster)
        target = EXPECTED[name]
        if current["logging_components"] != target["logging_components"]:
            values = option_values(tokens, "--logging")
            if not values or normalized_flag_components(values[-1], LOGGING_TO_API) != target["logging_components"]:
                errors.append(f"{name} command does not set the target logging components")
        if current["monitoring_components"] != target["monitoring_components"]:
            values = option_values(tokens, "--monitoring")
            if not values or normalized_flag_components(values[-1], MONITOR_TO_API) != target["monitoring_components"]:
                errors.append(f"{name} command does not set the target monitoring components")
        if current["managed_prometheus_enabled"] != target["managed_prometheus_enabled"]:
            required = "--enable-managed-prometheus" if target["managed_prometheus_enabled"] else "--disable-managed-prometheus"
            if required not in tokens:
                errors.append(f"{name} command omits {required}")
        if current["dataplane_v2_metrics_enabled"] != target["dataplane_v2_metrics_enabled"]:
            required = "--enable-dataplane-v2-flow-observability" if target["dataplane_v2_metrics_enabled"] else "--disable-dataplane-v2-flow-observability"
            if required not in tokens:
                errors.append(f"{name} command omits {required}")
        if current["logging_service"] != target["logging_service"]:
            if target["logging_service"] not in option_values(tokens, "--logging-service"):
                errors.append(f"{name} command does not restore the logging service")
        if current["monitoring_service"] != target["monitoring_service"]:
            if target["monitoring_service"] not in option_values(tokens, "--monitoring-service"):
                errors.append(f"{name} command does not restore the monitoring service")
    assert not errors, "; ".join(errors)


def test_command_safety_and_noop_handling():
    report = load_submission_or_skip()
    records, _ = cluster_records(report)
    errors = []
    for name, cluster in CLUSTER_BY_NAME.items():
        if name not in records:
            continue
        commands = apply_commands(records[name])
        if not has_drift(cluster) and commands:
            errors.append(f"{name} is compliant but receives a gratuitous update command")
        for command in commands:
            lowered = command.lower()
            if any(fragment in command for fragment in ("$(", "`", ";", "&&", "||", "<CLUSTER", "<PROJECT", "<REGION", "<ZONE")):
                errors.append(f"{name} command contains a payload, shell chain, or unresolved placeholder")
            if any(term in lowered for term in ("rm -rf", "curl ", "wget ")):
                errors.append(f"{name} command contains an unrelated unsafe operation")
            if "--enable-dataplane-v2-flow-observability" in lowered and not cluster["dataplane_v2"]:
                errors.append(f"{name} command enables metrics on a cluster without Dataplane V2")
    assert not errors, "; ".join(errors)


def test_dashboard_and_baseline_alerts():
    report = load_submission_or_skip()
    whole = normalized_text(report)
    assert "google cloud monitoring" in whole, "dashboards and alerts are not assigned to Google Cloud Monitoring"

    dashboard_contexts = [context for _, context in find_contexts(report, tuple(), "dashboard")]
    dashboards = " | ".join(dashboard_contexts)
    required_panels = (
        "apiserver request duration seconds",
        "container cpu usage seconds total",
        "container memory working set bytes",
        "kube pod container status restarts total",
        "scheduler scheduling duration seconds",
    )
    missing_panels = [metric for metric in required_panels if metric not in dashboards]
    assert not missing_panels, f"production dashboard omits required panels: {missing_panels}"
    assert "production" in dashboards or all(name in dashboards for name in PRODUCTION_NAMES), "dashboard scope does not cover the production fleet"

    api = find_contexts(report, ("apiserver request duration seconds", "p99"), "alert")
    assert any(re.search(r"(?:>|above|greater than|over)\s*5\s*(?:s|sec|second)", context) and ("production" in context or all(name in context for name in PRODUCTION_NAMES)) for _, context in api), "API latency alert is missing P99 > 5 seconds or production scope"
    crash = find_contexts(report, ("kube pod container status restarts total",), "alert")
    assert any("5" in context and re.search(r"10\s*(?:m|min|minute)", context) and ("production" in context or all(name in context for name in PRODUCTION_NAMES)) for _, context in crash), "crash-loop alert is missing >5 restarts in 10 minutes or production scope"
    scheduling = find_contexts(report, ("scheduler schedule attempts total",), "alert")
    assert any("error" in context and re.search(r"(?:>|above|greater than)\s*0", context) and ("production" in context or all(name in context for name in PRODUCTION_NAMES)) for _, context in scheduling), "scheduling-failure alert is missing result=error > 0 or production scope"


def test_composite_node_health_alert():
    report = load_submission_or_skip()
    contexts = find_contexts(
        report,
        ("kubernetes.io/node/status condition", "compute.googleapis.com/instance group/size"),
        "alert",
    )
    assert contexts, "no single node-health alert combines Ready status with managed instance-group size"
    assert any("ready" in context and ("less than" in context or "<" in context or "gap" in context) for _, context in contexts), (
        "the composite node-health alert does not compare Ready nodes with total managed nodes"
    )


def test_conditional_alert_and_panel_scope():
    report = load_submission_or_skip()
    pvc_names = {c["cluster_name"] for c in CLUSTERS if c["environment"] == "production" and c["persistent_volumes"]}
    gpu_names = {c["cluster_name"] for c in CLUSTERS if c["environment"] == "production" and c["gpu_nodes"]}

    pvc_alerts = find_contexts(report, ("kubelet volume stats used bytes", "kubelet volume stats capacity bytes"), "alert")
    assert any("85" in context and (pvc_names <= {name for name in CLUSTER_BY_NAME if name in context} or ("production" in context and "persistent" in context)) for _, context in pvc_alerts), (
        "PVC alert lacks the >85% condition or correct production-PVC scope"
    )
    gpu_alerts = find_contexts(report, ("dcgm fi dev gpu util",), "alert")
    assert any("95" in context and "sustain" in context and (gpu_names <= {name for name in CLUSTER_BY_NAME if name in context} or ("production" in context and "gpu" in context)) for _, context in gpu_alerts), (
        "GPU alert lacks the >95% sustained condition or correct production-GPU scope"
    )

    dashboard_contexts = [context for _, context in find_contexts(report, tuple(), "dashboard")]
    dashboards = " | ".join(dashboard_contexts)
    assert "kubelet volume stats used bytes" in dashboards and "kubelet volume stats capacity bytes" in dashboards, "dashboard omits PVC utilization"
    assert "dcgm fi dev gpu util" in dashboards, "dashboard omits GPU utilization"
