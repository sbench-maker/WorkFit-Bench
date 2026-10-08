from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


SUBMISSION = Path(os.environ.get("SUBMISSION_PROJECT", "/root/results/reservation_app"))
CANONICAL = Path(os.environ.get("CANONICAL_PROJECT", "/root/data/reservation_app"))
DART = os.environ.get("DART_BIN", "dart")
_BASELINE_RESULT: subprocess.CompletedProcess[str] | None = None


DECISION_MUTATIONS = [
    (
        "zero_quantity_is_accepted",
        "if (request.quantity <= 0)",
        "if (request.quantity < 0)",
    ),
    (
        "duplicate_request_falls_through",
        "if (existing != null) {",
        "if (existing != null && request.quantity == 999999) {",
    ),
    (
        "missing_stock_gets_wrong_reason",
        "reason: RejectionReason.unknownSku,",
        "reason: RejectionReason.insufficientStock,",
    ),
    (
        "inactive_stock_is_treated_as_active",
        "if (!stock.active) {",
        "if (stock.active) {",
    ),
    (
        "exact_availability_is_rejected",
        "if (available < request.quantity) {",
        "if (available <= request.quantity) {",
    ),
]


INTERACTION_MUTATIONS = [
    (
        "reserved_total_ignores_request",
        "final newReserved = stock.reserved + request.quantity;",
        "final newReserved = stock.reserved;",
    ),
    (
        "audit_write_is_skipped",
        "await database.appendAudit(\n",
        "if (false) await database.appendAudit(\n",
    ),
    (
        "audit_uses_a_different_timestamp",
        "recordedAt: createdAt,",
        "recordedAt: createdAt.add(const Duration(seconds: 1)),",
    ),
    (
        "insert_failure_does_not_restore_stock",
        "await database.updateReserved(request.sku, stock.reserved);",
        "await Future<void>.value();",
    ),
    (
        "reservation_is_inserted_before_stock_update",
        "await database.updateReserved(request.sku, newReserved);\n    try {\n      await database.insertReservation(entry);",
        "try {\n      await database.insertReservation(entry);\n      await database.updateReserved(request.sku, newReserved);",
    ),
]


def _run_dart(project: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [DART, "test", "--reporter=compact"],
            cwd=project,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=90,
            env={**os.environ, "PUB_ENVIRONMENT": "skillsbench_verifier"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess([DART, "test"], 127, stdout=str(exc))


def _submitted_test_files() -> list[Path]:
    test_dir = SUBMISSION / "test"
    if not test_dir.is_dir():
        return []
    return sorted(test_dir.rglob("*_test.dart"))


def _submitted_mock_files() -> list[Path]:
    test_dir = SUBMISSION / "test"
    if not test_dir.is_dir():
        return []
    return sorted(test_dir.rglob("*.mocks.dart"))


def _make_harness() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    holder = tempfile.TemporaryDirectory(prefix="reservation-verifier-")
    project = Path(holder.name) / "reservation_app"
    shutil.copytree(CANONICAL, project)
    submission_test = SUBMISSION / "test"
    if (project / "test").exists():
        shutil.rmtree(project / "test")
    if submission_test.is_dir():
        shutil.copytree(submission_test, project / "test")
    else:
        (project / "test").mkdir(parents=True)
    return holder, project


def _baseline_result() -> subprocess.CompletedProcess[str]:
    global _BASELINE_RESULT
    if _BASELINE_RESULT is None:
        holder, project = _make_harness()
        try:
            _BASELINE_RESULT = _run_dart(project)
        finally:
            holder.cleanup()
    return _BASELINE_RESULT


def _mutated_result(old: str, new: str) -> subprocess.CompletedProcess[str]:
    holder, project = _make_harness()
    try:
        service = project / "lib" / "reservation_service.dart"
        source = service.read_text(encoding="utf-8")
        count = source.count(old)
        assert count == 1, f"verifier mutation anchor appears {count} times: {old!r}"
        service.write_text(source.replace(old, new, 1), encoding="utf-8")
        return _run_dart(project)
    finally:
        holder.cleanup()


def test_artifact_and_generated_mock_suite_are_usable() -> None:
    assert SUBMISSION.is_dir(), (
        f"missing project directory {SUBMISSION}; the requested test deliverable cannot run"
    )
    test_files = _submitted_test_files()
    mock_files = _submitted_mock_files()
    assert test_files, "no Dart *_test.dart source was submitted"
    assert mock_files, "no generated .mocks.dart companion was included"

    tests_text = "\n".join(path.read_text(encoding="utf-8") for path in test_files)
    mocks_text = "\n".join(path.read_text(encoding="utf-8") for path in mock_files)
    assert "GenerateNiceMocks" in tests_text or "GenerateMocks" in tests_text, (
        "the test source has no Mockito generation annotation"
    )
    assert ".mocks.dart" in tests_text, "the suite does not import generated mock source"
    assert "MockInventoryDatabase" in tests_text, (
        "the tests do not instantiate or otherwise use the generated database mock"
    )
    assert "MockInventoryDatabase" in mocks_text, (
        "generated sources do not contain a mock for InventoryDatabase"
    )

    result = _baseline_result()
    assert result.returncode == 0, (
        "the submitted generated-mock suite does not pass against the supplied service:\n"
        + result.stdout[-5000:]
    )


@pytest.mark.parametrize("mutation_name,old,new", DECISION_MUTATIONS, ids=[m[0] for m in DECISION_MUTATIONS])
def test_decision_rule_mutations_are_detected(
    mutation_name: str, old: str, new: str
) -> None:
    baseline = _baseline_result()
    assert baseline.returncode == 0, (
        "mutation protection cannot be credited because the unmodified supplied service does not pass:\n"
        + baseline.stdout[-5000:]
    )
    result = _mutated_result(old, new)
    assert result.returncode != 0, (
        f"the suite passed with decision regression {mutation_name}; it does not protect the documented rule"
    )


@pytest.mark.parametrize(
    "mutation_name,old,new", INTERACTION_MUTATIONS, ids=[m[0] for m in INTERACTION_MUTATIONS]
)
def test_database_interaction_mutations_are_detected(
    mutation_name: str, old: str, new: str
) -> None:
    baseline = _baseline_result()
    assert baseline.returncode == 0, (
        "mutation protection cannot be credited because the unmodified supplied service does not pass:\n"
        + baseline.stdout[-5000:]
    )
    result = _mutated_result(old, new)
    assert result.returncode != 0, (
        f"the suite passed with database regression {mutation_name}; a material write, ordering, or recovery contract is unprotected"
    )
