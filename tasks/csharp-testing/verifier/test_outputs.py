from __future__ import annotations

from dataclasses import dataclass
import functools
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import pytest


SUBMISSION = Path(os.environ.get("SUBMISSION_ROOT", "/root/results/ParcelPilot"))
SOURCE = Path(os.environ.get("DATA_ROOT", "/root/data/ParcelPilot"))
SERVICE_REL = Path("src/ParcelPilot/Reservations/InventoryReservationService.cs")


@dataclass(frozen=True)
class RunResult:
    returncode: int
    total: int
    passed: int
    failed: int
    output: str

    @property
    def baseline_ok(self) -> bool:
        return self.returncode == 0 and self.total > 0 and self.passed > 0 and self.failed == 0

    @property
    def caught_mutant(self) -> bool:
        return self.returncode != 0 and self.total > 0 and self.failed > 0


MUTATIONS: dict[str, list[tuple[str, str]]] = {
    "quantity_51_allowed": [
        ("line.Quantity is < 1 or > 50", "line.Quantity is < 1 or > 51"),
    ],
    "whitespace_sku_allowed": [
        ("string.IsNullOrWhiteSpace(line.Sku)", "line.Sku is null"),
    ],
    "empty_lines_allowed": [
        (
            "request.Lines is null || request.Lines.Count == 0",
            "request.Lines is null",
        ),
    ],
    "stock_equality_rejected": [
        ("available < line.Value", "available <= line.Value"),
    ],
    "case_sensitive_duplicates": [
        ("StringComparer.OrdinalIgnoreCase", "StringComparer.Ordinal"),
        ("line.Sku.Trim().ToUpperInvariant()", "line.Sku.Trim()"),
    ],
    "sku_whitespace_not_normalized": [
        ("line.Sku.Trim().ToUpperInvariant()", "line.Sku.ToUpperInvariant()"),
    ],
    "duplicate_quantity_overwritten": [
        (
            "grouped.GetValueOrDefault(sku) + line.Quantity",
            "line.Quantity",
        ),
    ],
    "commit_omitted": [
        (
            """await _gateway.CommitAsync(
            request.RequestId.Trim(),
            warehouse,
            reservedLines,
            cancellationToken);""",
            "await Task.CompletedTask;",
        ),
    ],
    "request_id_not_trimmed": [
        ("request.RequestId.Trim()", "request.RequestId"),
    ],
    "total_is_distinct_sku_count": [
        ("grouped.Values.Sum()", "grouped.Count"),
    ],
    "pre_cancel_check_omitted": [
        ("cancellationToken.ThrowIfCancellationRequested();", ""),
    ],
    "lookup_token_discarded": [
        (
            """var available = await _gateway.GetAvailableAsync(
                warehouse,
                line.Key,
                cancellationToken);""",
            """var available = await _gateway.GetAvailableAsync(
                warehouse,
                line.Key,
                CancellationToken.None);""",
        ),
    ],
    "commit_token_discarded": [
        (
            """request.RequestId.Trim(),
            warehouse,
            reservedLines,
            cancellationToken);""",
            """request.RequestId.Trim(),
            warehouse,
            reservedLines,
            CancellationToken.None);""",
        ),
    ],
}


def _trx_counts(path: Path) -> tuple[int, int, int]:
    if not path.is_file():
        return 0, 0, 0
    root = ET.parse(path).getroot()
    results = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "UnitTestResult"]
    total = len(results)
    passed = sum(node.attrib.get("outcome", "").lower() == "passed" for node in results)
    failed = sum(node.attrib.get("outcome", "").lower() == "failed" for node in results)
    return total, passed, failed


def _replace_exact(text: str, before: str, after: str, mutation: str) -> str:
    count = text.count(before)
    if count != 1:
        raise AssertionError(
            f"verifier mutation {mutation!r} expected one source anchor, found {count}"
        )
    return text.replace(before, after, 1)


def _copy_clean_submission(destination: Path) -> None:
    shutil.copytree(SUBMISSION, destination)
    for path in list(destination.rglob("bin")) + list(destination.rglob("obj")):
        if path.is_dir():
            shutil.rmtree(path)
    submitted_src = destination / "src"
    if submitted_src.exists():
        shutil.rmtree(submitted_src)
    shutil.copytree(SOURCE / "src", submitted_src)


@functools.lru_cache(maxsize=None)
def _run_suite(variant: str) -> RunResult:
    if not SUBMISSION.is_dir():
        return RunResult(2, 0, 0, 0, "submission directory is missing")
    run_root = Path(tempfile.mkdtemp(prefix=f"parcelpilot-{variant}-"))
    repo = run_root / "ParcelPilot"
    try:
        _copy_clean_submission(repo)
        service_path = repo / SERVICE_REL
        if not service_path.is_file():
            return RunResult(2, 0, 0, 0, "production service is missing after fixture reset")
        if variant != "baseline":
            source = service_path.read_text(encoding="utf-8")
            for before, after in MUTATIONS[variant]:
                source = _replace_exact(source, before, after, variant)
            service_path.write_text(source, encoding="utf-8")

        env = os.environ.copy()
        env.update(
            {
                "DOTNET_CLI_HOME": str(run_root / "dotnet-home"),
                "DOTNET_NOLOGO": "1",
                "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
                "NUGET_PACKAGES": "/opt/nuget",
                "NUGET_XMLDOC_MODE": "skip",
            }
        )
        restore = subprocess.run(
            [
                "dotnet",
                "restore",
                str(repo / "ParcelPilot.sln"),
                "--packages",
                "/opt/nuget",
                "--ignore-failed-sources",
            ],
            cwd=repo,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=90,
        )
        if restore.returncode != 0:
            return RunResult(restore.returncode, 0, 0, 0, restore.stdout[-12000:])

        results = run_root / "TestResults"
        completed = subprocess.run(
            [
                "dotnet",
                "test",
                str(repo / "ParcelPilot.sln"),
                "--no-restore",
                "--configuration",
                "Release",
                "--logger",
                "trx;LogFileName=results.trx",
                "--results-directory",
                str(results),
                "--verbosity",
                "minimal",
            ],
            cwd=repo,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=90,
        )
        trx_files = sorted(results.rglob("results.trx"))
        total, passed, failed = _trx_counts(trx_files[0]) if trx_files else (0, 0, 0)
        return RunResult(completed.returncode, total, passed, failed, completed.stdout[-12000:])
    except (OSError, subprocess.TimeoutExpired, ET.ParseError, AssertionError) as exc:
        return RunResult(2, 0, 0, 0, f"{type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(run_root, ignore_errors=True)


def _assert_caught(mutation: str) -> None:
    baseline = _run_suite("baseline")
    if not baseline.baseline_ok:
        pytest.fail(
            "the submitted suite must compile, discover tests, and pass against the supplied "
            f"implementation before regression strength can be measured:\n{baseline.output}"
        )
    result = _run_suite(mutation)
    assert result.caught_mutant, (
        f"the suite did not produce a test failure for the {mutation.replace('_', ' ')} regression; "
        "the public contract is not protected against this change. "
        f"Runner summary: rc={result.returncode}, total={result.total}, "
        f"passed={result.passed}, failed={result.failed}\n{result.output}"
    )


def test_suite_builds_and_passes_baseline():
    assert SUBMISSION.is_dir(), "the requested /root/results/ParcelPilot repository is missing"
    required = [
        Path("ParcelPilot.sln"),
        Path("tests/ParcelPilot.Tests/ParcelPilot.Tests.csproj"),
        SERVICE_REL,
    ]
    missing = [str(path) for path in required if not (SUBMISSION / path).is_file()]
    assert not missing, f"the completed repository is missing required project files: {missing}"
    for source_path in sorted((SOURCE / "src").rglob("*")):
        if source_path.is_file():
            relative = source_path.relative_to(SOURCE)
            if any(part in {"bin", "obj"} for part in relative.parts):
                continue
            submitted_path = SUBMISSION / relative
            assert submitted_path.is_file(), f"production file {relative} was removed"
            assert submitted_path.read_bytes() == source_path.read_bytes(), (
                f"production file {relative} was changed even though the request was for tests only"
            )
    baseline = _run_suite("baseline")
    assert baseline.baseline_ok, (
        "dotnet test must compile, discover at least one test, and pass against the supplied "
        f"production behavior; rc={baseline.returncode}, total={baseline.total}, "
        f"passed={baseline.passed}, failed={baseline.failed}\n{baseline.output}"
    )


@pytest.mark.parametrize(
    "mutation",
    ["quantity_51_allowed", "whitespace_sku_allowed", "empty_lines_allowed"],
)
def test_validation_boundaries_and_no_gateway_side_effects(mutation: str):
    _assert_caught(mutation)


@pytest.mark.parametrize(
    "mutation",
    [
        "stock_equality_rejected",
        "case_sensitive_duplicates",
        "sku_whitespace_not_normalized",
        "duplicate_quantity_overwritten",
    ],
)
def test_inventory_grouping_and_availability_decisions(mutation: str):
    _assert_caught(mutation)


@pytest.mark.parametrize(
    "mutation",
    ["commit_omitted", "request_id_not_trimmed", "total_is_distinct_sku_count"],
)
def test_commit_contract_and_success_result(mutation: str):
    _assert_caught(mutation)


@pytest.mark.parametrize(
    "mutation",
    ["pre_cancel_check_omitted", "lookup_token_discarded", "commit_token_discarded"],
)
def test_cancellation_contract(mutation: str):
    _assert_caught(mutation)
