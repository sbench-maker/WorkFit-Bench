from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest
import yaml


OUTPUT = Path(os.environ.get("TASK_OUTPUT_DIR", "/root/results/gke-onboarding"))
DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))


def _load_brief() -> dict[str, Any]:
    return json.loads((DATA / "deployment-brief.json").read_text(encoding="utf-8"))


def _dockerfile_path() -> Path | None:
    if not OUTPUT.is_dir():
        return None
    matches = [path for path in OUTPUT.rglob("*") if path.is_file() and path.name.lower() == "dockerfile"]
    return min(matches, key=lambda path: (len(path.parts), str(path))) if matches else None


def _yaml_state() -> tuple[list[dict[str, Any]], list[str]]:
    documents: list[dict[str, Any]] = []
    errors: list[str] = []
    if not OUTPUT.is_dir():
        return documents, [f"output directory does not exist: {OUTPUT}"]
    yaml_paths = sorted(path for path in OUTPUT.rglob("*") if path.suffix.lower() in {".yaml", ".yml"})
    if not yaml_paths:
        return documents, ["no .yaml or .yml manifest was found"]
    for path in yaml_paths:
        try:
            loaded = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            errors.append(f"{path.relative_to(OUTPUT)} is not readable Kubernetes YAML: {exc}")
            continue
        for index, document in enumerate(loaded, start=1):
            if document is None:
                continue
            if not isinstance(document, dict):
                errors.append(f"{path.relative_to(OUTPUT)} document {index} is not a mapping")
                continue
            documents.append(document)
    return documents, errors


def _kind(document: dict[str, Any]) -> str:
    return str(document.get("kind", "")).strip().lower()


def _name(document: dict[str, Any]) -> str:
    metadata = document.get("metadata")
    return str(metadata.get("name", "")) if isinstance(metadata, dict) else ""


def _resource(documents: list[dict[str, Any]], kind: str, name: str) -> dict[str, Any] | None:
    exact = [doc for doc in documents if _kind(doc) == kind.lower() and _name(doc) == name]
    return exact[0] if len(exact) == 1 else None


def _deployment_parts(deployment: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    spec = deployment.get("spec") if isinstance(deployment.get("spec"), dict) else {}
    template = spec.get("template") if isinstance(spec.get("template"), dict) else {}
    pod_spec = template.get("spec") if isinstance(template.get("spec"), dict) else {}
    containers = pod_spec.get("containers") if isinstance(pod_spec.get("containers"), list) else []
    container = next((item for item in containers if isinstance(item, dict) and item.get("name") == "people-directory"), None)
    if container is None:
        container = next((item for item in containers if isinstance(item, dict)), {})
    return spec, pod_spec, container


def _cpu_millicores(value: Any) -> float | None:
    try:
        text = str(value).strip()
        return float(text[:-1]) if text.endswith("m") else float(text) * 1000
    except (TypeError, ValueError):
        return None


def _memory_bytes(value: Any) -> float | None:
    factors = {
        "Ki": 1024,
        "Mi": 1024**2,
        "Gi": 1024**3,
        "K": 1000,
        "M": 1000**2,
        "G": 1000**3,
    }
    try:
        text = str(value).strip()
        for suffix, factor in factors.items():
            if text.endswith(suffix):
                return float(text[: -len(suffix)]) * factor
        return float(text)
    except (TypeError, ValueError):
        return None


def _intish(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _env_by_name(container: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = container.get("env") if isinstance(container.get("env"), list) else []
    return {
        str(row.get("name")): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }


def _port_names(container: dict[str, Any]) -> dict[str, int]:
    rows = container.get("ports") if isinstance(container.get("ports"), list) else []
    result: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict) or _intish(row.get("containerPort")) is None:
            continue
        result[str(row.get("name", ""))] = int(_intish(row["containerPort"]))
    return result


def _probe_matches(container: dict[str, Any], probe_name: str, path: str, port: int) -> bool:
    probe = container.get(probe_name)
    if not isinstance(probe, dict):
        return False
    http_get = probe.get("httpGet")
    if not isinstance(http_get, dict) or http_get.get("path") != path:
        return False
    actual_port = http_get.get("port")
    if _intish(actual_port) == port:
        return True
    return isinstance(actual_port, str) and _port_names(container).get(actual_port) == port


def _manifest_or_skip() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    documents, errors = _yaml_state()
    if errors:
        pytest.skip("manifest syntax/readability is reported by test_artifact_usability")
    brief = _load_brief()
    deployment = _resource(documents, "deployment", brief["application"]["workload_name"])
    assert deployment is not None, "the brief's people-directory Deployment is missing or duplicated"
    return documents, deployment


def test_container_build_contract():
    brief = _load_brief()
    dockerfile = _dockerfile_path()
    assert dockerfile is not None, "the production Dockerfile is missing"
    text = dockerfile.read_text(encoding="utf-8")
    logical = re.sub(r"\\\s*\n", " ", text)
    active = "\n".join(line.split("#", 1)[0] for line in logical.splitlines())
    lower = active.lower()

    from_refs = re.findall(r"(?im)^\s*from\s+(?:--platform=\S+\s+)?(\S+)", active)
    node_refs = [ref for ref in from_refs if "node" in ref.lower()]
    assert node_refs, "the container stages do not provide the Node.js runtime required by package.json"
    assert any(re.search(r"(?:node[:/@-]|nodejs)[^\s]*20", ref, re.IGNORECASE) for ref in node_refs), (
        "the image does not use the app's required Node 20 runtime"
    )
    assert any("@sha256:" in ref.lower() or re.search(r"20\.\d+\.\d+", ref) for ref in node_refs), (
        "the Node base image is not pinned to a patch version or digest"
    )
    assert re.search(r"(?im)^\s*run\s+[^\n]*npm\s+(?:ci|install)\b", active), (
        "the Dockerfile never installs the package-lock-defined runtime dependencies"
    )
    assert "package" in lower and re.search(r"(?im)^\s*copy\s+[^\n]*(?:src|\.\s+\.)", active), (
        "the Dockerfile does not copy both package metadata and application source"
    )
    assert re.search(r"(?im)^\s*(?:expose\s+8080|env\s+port\s*=?.*8080)", active), (
        "the image does not declare the service's port 8080"
    )
    assert re.search(r"(?im)^\s*(?:cmd|entrypoint)\s+[^\n]*(?:npm[^\n]*start|node[^\n]*server\.js)", active), (
        "the image command does not start the supplied service"
    )
    users = re.findall(r"(?im)^\s*user\s+([^\s]+)", active)
    assert users and users[-1].lower() not in {"0", "root", "0:0", "root:root"}, (
        "the final container stage does not switch to a non-root user"
    )

    generic_copy = bool(re.search(r"(?im)^\s*(?:copy|add)\s+(?:--\S+\s+)*[\"']?\.[\"']?\s+[\"']?\.?/?[\"']?\s*$", active))
    if generic_copy:
        ignore_path = dockerfile.parent / ".dockerignore"
        ignore = ignore_path.read_text(encoding="utf-8").lower() if ignore_path.is_file() else ""
        assert any(pattern in ignore for pattern in ("fixtures", "*.sample.json", "staff-directory.sample.json")), (
            "a whole-context COPY would bake the local-only staff fixture into the image because .dockerignore does not exclude it"
        )
    assert "staff-directory.sample.json" not in lower and "fixtures/" not in lower, (
        "the Dockerfile explicitly copies the fictional staff fixture into the production image"
    )


def test_deployment_identity_and_resources():
    brief = _load_brief()
    _, deployment = _manifest_or_skip()
    app = brief["application"]
    spec, _, container = _deployment_parts(deployment)
    metadata = deployment.get("metadata") if isinstance(deployment.get("metadata"), dict) else {}

    assert metadata.get("namespace") == brief["target"]["namespace"], "the Deployment targets the wrong namespace"
    assert _intish(spec.get("replicas")) == app["replicas"], "the Deployment does not carry through the required three replicas"
    assert container.get("image") == app["image"], "the Deployment does not use the brief's immutable image digest"
    assert 8080 in _port_names(container).values(), "the container does not declare its actual port 8080"

    resources = container.get("resources") if isinstance(container.get("resources"), dict) else {}
    requests = resources.get("requests") if isinstance(resources.get("requests"), dict) else {}
    limits = resources.get("limits") if isinstance(resources.get("limits"), dict) else {}
    expected = brief["resources"]
    assert _cpu_millicores(requests.get("cpu")) == _cpu_millicores(expected["requests"]["cpu"]), "CPU request differs from the reviewed policy"
    assert _memory_bytes(requests.get("memory")) == _memory_bytes(expected["requests"]["memory"]), "memory request differs from the reviewed policy"
    assert _cpu_millicores(limits.get("cpu")) == _cpu_millicores(expected["limits"]["cpu"]), "CPU limit differs from the reviewed policy"
    assert _memory_bytes(limits.get("memory")) == _memory_bytes(expected["limits"]["memory"]), "memory limit differs from the reviewed policy"


def test_health_and_rollout_contract():
    brief = _load_brief()
    _, deployment = _manifest_or_skip()
    spec, pod_spec, container = _deployment_parts(deployment)
    health = brief["health"]

    assert _probe_matches(container, "livenessProbe", health["liveness_path"], 8080), (
        "livenessProbe is not wired to the application's /livez endpoint on port 8080"
    )
    assert _probe_matches(container, "readinessProbe", health["readiness_path"], 8080), (
        "readinessProbe is not wired to the data-dependent /readyz endpoint on port 8080"
    )
    assert _intish(container["livenessProbe"].get("initialDelaySeconds", 0)) >= health["initial_delay_seconds"]["liveness"], (
        "liveness begins before the brief's startup allowance"
    )
    assert _intish(container["readinessProbe"].get("initialDelaySeconds", 0)) >= health["initial_delay_seconds"]["readiness"], (
        "readiness begins before the brief's data-load allowance"
    )
    assert _intish(pod_spec.get("terminationGracePeriodSeconds")) == brief["rollout"]["termination_grace_period_seconds"], (
        "the Deployment omits the required graceful-shutdown window"
    )
    strategy = spec.get("strategy") if isinstance(spec.get("strategy"), dict) else {}
    rolling = strategy.get("rollingUpdate") if isinstance(strategy.get("rollingUpdate"), dict) else {}
    assert str(strategy.get("type", "RollingUpdate")).lower() == "rollingupdate", "the Deployment is not configured for a rolling update"
    assert _intish(rolling.get("maxUnavailable")) == 0, "rolling updates may make an HR directory replica unavailable"
    assert _intish(rolling.get("maxSurge")) == 1, "maxSurge differs from the reviewed rollout policy"


def test_runtime_configuration_and_data_mounts():
    brief = _load_brief()
    _, deployment = _manifest_or_skip()
    _, pod_spec, container = _deployment_parts(deployment)
    runtime = brief["runtime"]
    env = _env_by_name(container)

    for name, expected in runtime["literal_environment"].items():
        assert name in env and str(env[name].get("value")) == expected, f"{name} does not match the app runtime contract"
    app_mode_ref = env.get("APP_MODE", {}).get("valueFrom", {}).get("configMapKeyRef", {})
    expected_mode = runtime["config_map_environment"]["APP_MODE"]
    assert app_mode_ref.get("name") == expected_mode["name"] and app_mode_ref.get("key") == expected_mode["key"], (
        "APP_MODE does not reference the existing runtime ConfigMap key"
    )
    secret_ref = env.get("SESSION_SIGNING_KEY", {}).get("valueFrom", {}).get("secretKeyRef", {})
    expected_secret = runtime["secret_environment"]["SESSION_SIGNING_KEY"]
    assert secret_ref.get("name") == expected_secret["name"] and secret_ref.get("key") == expected_secret["key"], (
        "SESSION_SIGNING_KEY does not reference the existing Secret key"
    )

    volumes = {
        str(row.get("name")): row
        for row in (pod_spec.get("volumes") if isinstance(pod_spec.get("volumes"), list) else [])
        if isinstance(row, dict) and row.get("name")
    }
    mounts = {
        str(row.get("name")): row
        for row in (container.get("volumeMounts") if isinstance(container.get("volumeMounts"), list) else [])
        if isinstance(row, dict) and row.get("name")
    }
    staff_candidates = []
    for volume_name, volume in volumes.items():
        config = volume.get("configMap")
        if isinstance(config, dict) and config.get("name") == runtime["staff_data"]["config_map"]:
            staff_candidates.append((volume_name, config, mounts.get(volume_name, {})))
    assert len(staff_candidates) == 1, "the existing staff ConfigMap is not mounted exactly once"
    _, config, staff_mount = staff_candidates[0]
    items = config.get("items") if isinstance(config.get("items"), list) else []
    if items:
        assert any(
            isinstance(item, dict)
            and item.get("key") == runtime["staff_data"]["key"]
            and str(item.get("path", runtime["staff_data"]["key"])).endswith("directory.json")
            for item in items
        ), "the staff ConfigMap mount does not expose its directory.json key"
    staff_mount_path = str(staff_mount.get("mountPath", ""))
    effective_staff_path = (
        staff_mount_path
        if staff_mount.get("subPath")
        else staff_mount_path.rstrip("/") + "/directory.json"
    )
    assert effective_staff_path == runtime["staff_data"]["mount_path"], "staff data is not mounted at STAFF_DATA_PATH"
    assert staff_mount.get("readOnly") is True, "the staff data mount is not read-only"

    cache_path = runtime["writable_cache_path"]
    cache_mounts = []
    for volume_name, mount in mounts.items():
        mount_path = str(mount.get("mountPath", "")).rstrip("/")
        if cache_path == mount_path or cache_path.startswith(mount_path + "/"):
            cache_mounts.append(volumes.get(volume_name, {}))
    assert any("emptyDir" in volume for volume in cache_mounts), (
        "CACHE_DIR has no writable emptyDir mount, so startup would fail with a read-only root filesystem"
    )


def test_pod_security_and_no_embedded_secrets():
    brief = _load_brief()
    documents, deployment = _manifest_or_skip()
    _, pod_spec, container = _deployment_parts(deployment)
    pod_security = pod_spec.get("securityContext") if isinstance(pod_spec.get("securityContext"), dict) else {}
    container_security = container.get("securityContext") if isinstance(container.get("securityContext"), dict) else {}

    assert pod_spec.get("automountServiceAccountToken") is False, "the pod unnecessarily automounts a service-account token"
    assert pod_security.get("runAsNonRoot") is True, "the pod is not required to run as non-root"
    seccomp = pod_security.get("seccompProfile") if isinstance(pod_security.get("seccompProfile"), dict) else {}
    assert seccomp.get("type") == brief["security"]["seccomp_profile"], "the required RuntimeDefault seccomp profile is absent"
    assert container_security.get("allowPrivilegeEscalation") is False, "the container can enable privilege escalation"
    assert container_security.get("readOnlyRootFilesystem") is True, "the production container root filesystem is writable"
    capabilities = container_security.get("capabilities") if isinstance(container_security.get("capabilities"), dict) else {}
    dropped = {str(value).upper() for value in capabilities.get("drop", [])} if isinstance(capabilities.get("drop"), list) else set()
    assert "ALL" in dropped, "Linux capabilities are not dropped"

    env = _env_by_name(container)
    signing = env.get("SESSION_SIGNING_KEY", {})
    assert "value" not in signing and isinstance(signing.get("valueFrom"), dict), (
        "SESSION_SIGNING_KEY is embedded as a literal rather than referenced from the existing Secret"
    )
    forbidden_objects = {
        (kind.lower(), name)
        for kind, name in (
            ("Secret", "hr-directory-secrets"),
            ("ConfigMap", "hr-directory-runtime"),
            ("ConfigMap", "hr-directory-staff"),
        )
    }
    recreated = {(_kind(document), _name(document)) for document in documents} & forbidden_objects
    assert not recreated, f"the bundle recreates platform-managed objects instead of referencing them: {sorted(recreated)}"


def test_internal_service_wiring():
    brief = _load_brief()
    documents, deployment = _manifest_or_skip()
    service = _resource(documents, "service", brief["application"]["service_name"])
    assert service is not None, "the brief's people-directory Service is missing or duplicated"
    metadata = service.get("metadata") if isinstance(service.get("metadata"), dict) else {}
    service_spec = service.get("spec") if isinstance(service.get("spec"), dict) else {}
    _, _, container = _deployment_parts(deployment)
    deployment_spec = deployment.get("spec") if isinstance(deployment.get("spec"), dict) else {}
    template = deployment_spec.get("template") if isinstance(deployment_spec.get("template"), dict) else {}
    template_metadata = template.get("metadata") if isinstance(template.get("metadata"), dict) else {}
    pod_labels = template_metadata.get("labels") if isinstance(template_metadata.get("labels"), dict) else {}

    assert metadata.get("namespace") == brief["target"]["namespace"], "the Service targets the wrong namespace"
    service_type = str(service_spec.get("type", "ClusterIP"))
    assert service_type.lower() == "clusterip", "the HR service is externally exposed instead of using ClusterIP"
    assert not service_spec.get("externalIPs") and not service_spec.get("loadBalancerIP"), "the Service includes an external address"
    selector = service_spec.get("selector") if isinstance(service_spec.get("selector"), dict) else {}
    assert selector and all(pod_labels.get(key) == value for key, value in selector.items()), (
        "the Service selector does not match the Deployment pod labels"
    )

    ports = service_spec.get("ports") if isinstance(service_spec.get("ports"), list) else []
    route = next((row for row in ports if isinstance(row, dict) and _intish(row.get("port")) == 80), None)
    assert route is not None, "the Service does not provide its required port 80"
    target = route.get("targetPort", route.get("port"))
    target_value = _intish(target)
    if target_value is None and isinstance(target, str):
        target_value = _port_names(container).get(target)
    assert target_value == 8080, "Service port 80 does not resolve to the application's port 8080"

    external_kinds = {"ingress", "gateway", "httproute"}
    found_external = sorted({_kind(document) for document in documents} & external_kinds)
    assert not found_external, f"the bundle adds externally exposing resources: {found_external}"
