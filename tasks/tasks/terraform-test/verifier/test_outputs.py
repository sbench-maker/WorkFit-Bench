from __future__ import annotations

from dataclasses import dataclass
import functools
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


SUBMISSION = Path(
    os.environ.get(
        "SUBMISSION_FILE",
        "/root/results/edge_delivery_unit_test.tftest.hcl",
    )
)
SOURCE = Path(os.environ.get("DATA_ROOT", "/root/data/edge_delivery"))


@dataclass(frozen=True)
class RunResult:
    returncode: int
    run_count: int
    output: str

    @property
    def baseline_ok(self) -> bool:
        return self.returncode == 0 and self.run_count > 0

    @property
    def caught_mutant(self) -> bool:
        return self.returncode != 0


MUTATIONS: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "default_has_three_subnets": (
        "variables.tf",
        [("default     = 2", "default     = 3")],
    ),
    "subnet_cidr_sequence_shifted": (
        "main.tf",
        [
            (
                "cidrsubnet(var.network_cidr, 8, index + 10)",
                "cidrsubnet(var.network_cidr, 8, index + 11)",
            )
        ],
    ),
    "zone_rotation_removed": (
        "main.tf",
        [
            (
                "var.availability_zones[index % length(var.availability_zones)]",
                "var.availability_zones[0]",
            )
        ],
    ),
    "endpoints_always_created": (
        "main.tf",
        [
            (
                "count = var.enable_private_endpoints ? var.subnet_count : 0",
                "count = var.subnet_count",
            )
        ],
    ),
    "only_one_endpoint_created": (
        "main.tf",
        [
            (
                "count = var.enable_private_endpoints ? var.subnet_count : 0",
                "count = var.enable_private_endpoints ? 1 : 0",
            )
        ],
    ),
    "caller_overrides_protected_tags": (
        "main.tf",
        [
            (
                "merge(var.common_tags, local.reserved_tags)",
                "merge(local.reserved_tags, var.common_tags)",
            )
        ],
    ),
    "two_subnet_production_allowed": (
        "main.tf",
        [
            (
                'var.environment != "prod" || var.subnet_count >= 3',
                'var.environment != "prod" || var.subnet_count >= 2',
            )
        ],
    ),
    "qa_environment_allowed": (
        "variables.tf",
        [
            (
                '["dev", "staging", "prod"]',
                '["dev", "staging", "prod", "qa"]',
            )
        ],
    ),
    "seven_subnets_allowed": (
        "variables.tf",
        [
            (
                "var.subnet_count <= 6",
                "var.subnet_count <= 7",
            )
        ],
    ),
}


def _strip_hcl_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"(?m)^\s*(?:#|//).*?$", "", text)


def _run_count(text: str) -> int:
    clean = _strip_hcl_comments(text)
    return len(re.findall(r'\brun\s+"[^"]+"\s*\{', clean))


def _all_runs_are_explicit_plan(text: str) -> bool:
    clean = _strip_hcl_comments(text)
    run_count = _run_count(clean)
    plan_count = len(re.findall(r"\bcommand\s*=\s*plan\b", clean))
    non_plan = re.search(r"\bcommand\s*=\s*(?!plan\b)[A-Za-z_-]+", clean)
    return run_count > 0 and plan_count == run_count and non_plan is None


def _replace_exact(text: str, before: str, after: str, mutation: str) -> str:
    count = text.count(before)
    if count != 1:
        raise AssertionError(
            f"verifier mutation {mutation!r} expected one source anchor, found {count}"
        )
    return text.replace(before, after, 1)


@functools.lru_cache(maxsize=None)
def _run_suite(variant: str) -> RunResult:
    if not SUBMISSION.is_file():
        return RunResult(2, 0, "submission test file is missing")
    if not SOURCE.is_dir():
        return RunResult(2, 0, "source module is missing")

    try:
        submitted_text = SUBMISSION.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return RunResult(2, 0, f"cannot read submission as UTF-8: {exc}")

    run_root = Path(tempfile.mkdtemp(prefix=f"edge-delivery-{variant}-"))
    module = run_root / "edge_delivery"
    try:
        shutil.copytree(SOURCE, module)
        tests_dir = module / "tests"
        # The task explicitly asks the agent to run Terraform tests, so a
        # pre-existing tests/ directory is valid submission state.
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "submission.tftest.hcl").write_text(submitted_text, encoding="utf-8")

        if variant != "baseline":
            relative, edits = MUTATIONS[variant]
            source_path = module / relative
            source_text = source_path.read_text(encoding="utf-8")
            for before, after in edits:
                source_text = _replace_exact(source_text, before, after, variant)
            source_path.write_text(source_text, encoding="utf-8")

        env = os.environ.copy()
        env.update(
            {
                "TF_IN_AUTOMATION": "1",
                "CHECKPOINT_DISABLE": "1",
            }
        )
        init = subprocess.run(
            [
                "terraform",
                "init",
                "-backend=false",
                "-input=false",
                "-no-color",
            ],
            cwd=module,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=45,
        )
        if init.returncode != 0:
            return RunResult(init.returncode, _run_count(submitted_text), init.stdout[-12000:])

        completed = subprocess.run(
            ["terraform", "test", "-test-directory=tests", "-no-color"],
            cwd=module,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
        )
        return RunResult(
            completed.returncode,
            _run_count(submitted_text),
            completed.stdout[-12000:],
        )
    except (OSError, subprocess.TimeoutExpired, AssertionError) as exc:
        return RunResult(2, _run_count(submitted_text), f"{type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(run_root, ignore_errors=True)


def _assert_caught(mutation: str) -> None:
    baseline = _run_suite("baseline")
    if not baseline.baseline_ok:
        pytest.fail(
            "the submitted suite must contain run blocks and pass against the supplied "
            f"module before regression strength can be measured:\n{baseline.output}"
        )
    result = _run_suite(mutation)
    assert result.caught_mutant, (
        f"the suite did not fail for the {mutation.replace('_', ' ')} regression; "
        "that part of the module contract is unprotected. "
        f"Runner return code: {result.returncode}\n{result.output}"
    )


def test_suite_is_runnable_and_plan_only():
    assert SUBMISSION.is_file(), (
        "the requested /root/results/edge_delivery_unit_test.tftest.hcl file is missing"
    )
    try:
        text = SUBMISSION.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        pytest.fail(f"the submitted Terraform test is not readable UTF-8 text: {exc}")
    assert _all_runs_are_explicit_plan(text), (
        "every run block must explicitly use command = plan; an omitted command defaults "
        "to apply and would make this pull-request suite unsafe"
    )
    baseline = _run_suite("baseline")
    assert baseline.baseline_ok, (
        "terraform test must discover at least one run and pass against the supplied module; "
        f"rc={baseline.returncode}, runs={baseline.run_count}\n{baseline.output}"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "default_has_three_subnets",
        "subnet_cidr_sequence_shifted",
        "zone_rotation_removed",
    ],
)
def test_topology_contract_is_protected(mutation: str):
    _assert_caught(mutation)


@pytest.mark.parametrize(
    "mutation",
    [
        "endpoints_always_created",
        "only_one_endpoint_created",
        "caller_overrides_protected_tags",
    ],
)
def test_conditional_endpoints_and_tags_are_protected(mutation: str):
    _assert_caught(mutation)


@pytest.mark.parametrize(
    "mutation",
    [
        "two_subnet_production_allowed",
        "qa_environment_allowed",
        "seven_subnets_allowed",
    ],
)
def test_validation_and_production_boundaries_are_protected(mutation: str):
    _assert_caught(mutation)
