from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
from typing import Optional
import urllib.request

import pytest


RESULT = Path("/root/results/playwright_project")
SOURCE_PROJECT = Path("/root/data/cypress_project")


MUTATIONS = {
    "standard_shipping": (
        "input.shipping === 'express' ? 1500 : (subtotal >= 10000 ? 0 : 500)",
        "input.shipping === 'express' ? 1500 : (subtotal >= 10000 ? 0 : 700)",
    ),
    "promo_discount": (
        "Math.round(subtotal * 0.10) : 0",
        "0 : 0",
    ),
    "express_shipping": (
        "input.shipping === 'express' ? 1500",
        "input.shipping === 'express' ? 2500",
    ),
    "out_of_stock": (
        "submit.disabled = !inStock;",
        "submit.disabled = false;",
    ),
    "pricing_error": (
        "show(error, 'Unable to price order. Try again.'); return;",
        "hide(error); return;",
    ),
    "receipt_popup": (
        'data-testid="receipt-link" target="_blank" rel="noopener"',
        'data-testid="receipt-link" rel="noopener"',
    ),
}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run_suite(mutation: Optional[str] = None) -> subprocess.CompletedProcess[str]:
    assert RESULT.is_dir(), "playwright_project is missing; the requested migration cannot be run"
    with tempfile.TemporaryDirectory(prefix="checkout-app-") as raw_tmp:
        project = Path(raw_tmp) / "cypress_project"
        execution_project = Path(raw_tmp) / "playwright_project"
        shutil.copytree(SOURCE_PROJECT, project)
        shutil.copytree(
            RESULT,
            execution_project,
            ignore=shutil.ignore_patterns("node_modules", "playwright-report", "test-results"),
        )
        if mutation:
            server_path = project / "app" / "server.js"
            server_text = server_path.read_text(encoding="utf-8")
            before, after = MUTATIONS[mutation]
            assert before in server_text, f"verifier mutation anchor is missing: {mutation}"
            server_path.write_text(server_text.replace(before, after), encoding="utf-8")

        port = _free_port()
        server_env = os.environ.copy()
        server_env["PORT"] = str(port)
        server = subprocess.Popen(
            ["node", str(project / "app" / "server.js")],
            cwd=project,
            env=server_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            deadline = time.monotonic() + 8
            while True:
                if server.poll() is not None:
                    output = server.stdout.read() if server.stdout else ""
                    raise AssertionError(f"fixture app exited before startup: {output}")
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/checkout", timeout=0.4) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    raise AssertionError("fixture app did not become ready")
                time.sleep(0.08)

            test_env = os.environ.copy()
            test_env["BASE_URL"] = f"http://127.0.0.1:{port}"
            test_env["CI"] = "1"
            return subprocess.run(
                ["playwright", "test", "--reporter=line", "--workers=1"],
                cwd=execution_project,
                env=test_env,
                capture_output=True,
                text=True,
                timeout=90,
            )
        finally:
            server.terminate()
            try:
                server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=3)


def _failure_context(run: subprocess.CompletedProcess[str]) -> str:
    combined = (run.stdout + "\n" + run.stderr).strip()
    return combined[-5000:]


def test_runnable_migration_passes_against_the_supplied_app():
    """The migrated project executes successfully and honors the supplied BASE_URL."""
    package_path = RESULT / "package.json"
    assert package_path.is_file(), "package.json is missing, so the migrated project has no runnable handoff"
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        pytest.fail(f"package.json is unreadable: {exc}")
    assert isinstance(package.get("scripts"), dict) and package["scripts"], (
        "package.json has no validation script for the migrated project"
    )
    run = _run_suite()
    assert run.returncode == 0, (
        "the submitted Playwright suite does not pass against the supplied checkout app or does not honor "
        f"BASE_URL; runner output:\n{_failure_context(run)}"
    )


@pytest.mark.parametrize("mutation", ["standard_shipping", "promo_discount", "express_shipping"])
def test_checkout_calculation_regressions_are_detected(mutation: str):
    """Material shipping and discount regressions must make the migrated suite fail."""
    run = _run_suite(mutation)
    assert run.returncode != 0, (
        f"the suite still passed when the {mutation} business rule was broken; it did not preserve that "
        "checkout calculation from the source suite"
    )


@pytest.mark.parametrize("mutation", ["out_of_stock", "pricing_error", "receipt_popup"])
def test_resilience_and_browser_event_regressions_are_detected(mutation: str):
    """Stock blocking, retry feedback, and real popup behavior remain protected."""
    run = _run_suite(mutation)
    assert run.returncode != 0, (
        f"the suite still passed when {mutation} behavior was broken; a user-visible source behavior was lost"
    )


def test_project_is_clean_playwright_typescript():
    """The deliverable is a TypeScript Playwright project without Cypress runtime residue."""
    assert RESULT.is_dir(), "playwright_project is missing"
    config_files = [path for path in RESULT.glob("playwright.config.*") if path.is_file()]
    test_files = [
        path for path in RESULT.rglob("*.ts")
        if "node_modules" not in path.parts and path.name not in {p.name for p in config_files}
    ]
    assert config_files, "no Playwright configuration was provided"
    assert test_files, "no TypeScript test source was provided"

    source_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in [*config_files, *test_files]
    )
    assert "@playwright/test" in source_text, "the TypeScript sources do not use Playwright Test"
    forbidden = ["cy.", "Cypress.", "from 'cypress'", 'from "cypress"']
    leftovers = [token for token in forbidden if token in source_text]
    assert not leftovers, f"Cypress-only source APIs remain in the migrated project: {leftovers}"

    package_path = RESULT / "package.json"
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        pytest.fail(f"package.json is unreadable: {exc}")
    dependencies = {}
    for field in ("dependencies", "devDependencies", "optionalDependencies"):
        values = package.get(field, {})
        if isinstance(values, dict):
            dependencies.update({str(key).lower(): value for key, value in values.items()})
    assert "@playwright/test" in dependencies, "package.json does not declare the Playwright Test dependency"
    assert dependencies["@playwright/test"] == "1.55.0", (
        "package.json must pin @playwright/test to the image-provided version 1.55.0"
    )
    assert dependencies.get("typescript") == "5.9.2", (
        "package.json must pin TypeScript to the image-provided version 5.9.2"
    )
    assert "cypress" not in dependencies, "package.json still carries the Cypress dependency"
    assert not (RESULT / "node_modules").exists(), (
        "do not install or deliver node_modules; the offline image provides the pinned Playwright toolchain"
    )
