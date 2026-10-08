from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import yaml


RESULTS = Path("/root/results/router_checkout")
DATA = Path("/root/data/router_checkout")
HIDDEN_TEST = Path("/verifier/verifier_contract.rs")
_PREPARED: Path | None = None


def _cargo() -> str:
    configured = Path(os.environ.get("CARGO_HOME", "/usr/local/cargo")) / "bin" / "cargo"
    if configured.is_file():
        return str(configured)
    return shutil.which("cargo") or "cargo"


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={
            **os.environ,
            "CARGO_NET_OFFLINE": "true",
            "PATH": str(Path(_cargo()).parent) + os.pathsep + os.environ.get("PATH", ""),
        },
        timeout=90,
    )


def _prepared_repo() -> Path:
    global _PREPARED
    if _PREPARED is not None:
        return _PREPARED
    assert RESULTS.is_dir(), (
        "the requested /root/results/router_checkout directory is missing; "
        "there is no plugin checkout to validate"
    )
    temp_root = Path(tempfile.mkdtemp(prefix="query-budget-verifier-"))
    target = temp_root / "router_checkout"
    shutil.copytree(RESULTS, target)
    tests_dir = target / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HIDDEN_TEST, tests_dir / "verifier_contract.rs")
    _PREPARED = target
    return target


def _cargo_test(test_name: str) -> None:
    repo = _prepared_repo()
    completed = _run(
        [_cargo(), "test", "--offline", "--test", "verifier_contract", test_name, "--", "--exact"],
        repo,
    )
    assert completed.returncode == 0, (
        f"the observable plugin contract failed in {test_name}; "
        f"the checkout is not safe to use for the staged load test\n{completed.stdout[-6000:]}"
    )


def _load_policy() -> dict:
    return json.loads((DATA / "policy/query_budget_policy.json").read_text(encoding="utf-8"))


def test_workspace_builds_and_required_artifacts_are_present():
    required = [
        RESULTS / "Cargo.toml",
        RESULTS / "src/plugins/query_budget.rs",
        RESULTS / "src/plugins/mod.rs",
        RESULTS / "config/router.yaml",
    ]
    missing = [str(path.relative_to(RESULTS)) for path in required if not path.is_file()]
    assert not missing, f"the copied checkout is missing required integration artifacts: {missing}"
    for path in required:
        path.read_text(encoding="utf-8")
    completed = _run([_cargo(), "check", "--offline", "--all-targets"], _prepared_repo())
    assert completed.returncode == 0, (
        "the submitted checkout does not compile with its local offline interfaces; "
        f"it cannot be integrated into the gateway\n{completed.stdout[-6000:]}"
    )


def test_router_hook_captures_normalized_tier():
    _cargo_test("verifier_router_capture")


def test_execution_enforces_configured_limits_and_error_contract():
    _cargo_test("verifier_execution_limits_and_errors")


def test_disabled_passthrough_boundaries_and_short_circuiting():
    _cargo_test("verifier_passthrough_and_short_circuit")


def test_registration_module_and_configuration_are_integrated():
    _cargo_test("verifier_registration")
    policy = _load_policy()
    config_path = RESULTS / "config/router.yaml"
    parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict) and isinstance(parsed.get("plugins"), dict), (
        "config/router.yaml must contain a usable plugins mapping"
    )
    plugin_key = f"{policy['namespace']}.{policy['plugin_name']}"
    settings = parsed["plugins"].get(plugin_key)
    assert isinstance(settings, dict), f"router config does not enable {plugin_key}"
    expected = {
        "enabled": policy["enabled"],
        "client_tier_header": policy["client_tier_header"],
        "default_tier": policy["default_tier"],
        "tier_limits": policy["tier_limits"],
        "mutation_max_cost": policy["mutation_max_cost"],
        "rejection_status": policy["rejection"]["http_status"],
        "error_code": policy["rejection"]["error_code"],
        "error_message": policy["rejection"]["message"],
    }
    mismatches = {
        key: {"expected": value, "actual": settings.get(key)}
        for key, value in expected.items()
        if settings.get(key) != value
    }
    assert not mismatches, (
        "the router configuration is inconsistent with the supplied policy; "
        f"mismatched settings: {mismatches!r}"
    )
