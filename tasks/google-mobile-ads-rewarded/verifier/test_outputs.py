from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


DATA_ROOT = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_ROOT = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
VERIFIER_ROOT = Path(os.environ.get("TASK_VERIFIER_DIR", "/verifier"))
OUTPUT = RESULTS_ROOT / "RewardedBoostController.java"
SOURCE_ROOT = DATA_ROOT / "android_app" / "app" / "src" / "main" / "java"
STARTER = SOURCE_ROOT / "com" / "asterlane" / "game" / "RewardedBoostController.java"
HARNESS = VERIFIER_ROOT / "java" / "IntegrationHarness.java"


@pytest.fixture(scope="session")
def compiled_project(tmp_path_factory):
    build_root = tmp_path_factory.mktemp("rewarded-java")
    classes = build_root / "classes"
    classes.mkdir()
    if not OUTPUT.is_file():
        return {"ok": False, "message": f"requested output is missing: {OUTPUT}", "classes": classes}
    try:
        source_text = OUTPUT.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return {"ok": False, "message": f"output is not readable UTF-8 Java source: {exc}", "classes": classes}
    if not source_text.strip():
        return {"ok": False, "message": "output Java source is empty", "classes": classes}

    sources = [path for path in SOURCE_ROOT.rglob("*.java") if path != STARTER]
    sources.extend([OUTPUT, HARNESS])
    completed = subprocess.run(
        ["javac", "-encoding", "UTF-8", "-d", str(classes), *map(str, sources)],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "javac failed without diagnostics"
        return {"ok": False, "message": message, "classes": classes}
    return {"ok": True, "message": "", "classes": classes}


def _run(compiled_project, scenario: str) -> str:
    if not compiled_project["ok"]:
        pytest.skip("artifact compile/readability failure is reported by the artifact criterion")
    completed = subprocess.run(
        ["java", "-cp", str(compiled_project["classes"]), "verifier.IntegrationHarness", scenario],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, (
        f"rewarded-ad scenario {scenario!r} failed: "
        f"{completed.stderr.strip() or completed.stdout.strip()}"
    )
    return completed.stdout


def test_artifact_compiles_and_preserves_contract(compiled_project):
    assert compiled_project["ok"], compiled_project["message"]
    assert "PASS smoke" in _run(compiled_project, "smoke")


def test_loading_and_readiness_state(compiled_project):
    assert "PASS loading" in _run(compiled_project, "loading")


def test_presentation_requires_explicit_opt_in(compiled_project):
    assert "PASS opt_in" in _run(compiled_project, "opt_in")


def test_reward_is_granted_only_when_earned(compiled_project):
    assert "PASS reward" in _run(compiled_project, "reward")


def test_callback_thread_safety_and_inventory_recovery(compiled_project):
    assert "PASS recovery" in _run(compiled_project, "recovery")
