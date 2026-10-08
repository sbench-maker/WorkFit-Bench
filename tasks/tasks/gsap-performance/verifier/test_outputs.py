from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Optional

import pytest


ROOT = Path(os.environ.get("TASK_ROOT", "/root"))
DATA_PROJECT = ROOT / "data" / "project"
PATCH = ROOT / "results" / "gsap-fix.patch"
REPORT = ROOT / "results" / "performance-review.md"
PROBE = Path(__file__).with_name("runtime_probe.mjs")


@dataclass(frozen=True)
class Submission:
    project: Optional[Path]
    error: Optional[str]


def _safe_patch_paths(text: str) -> Optional[str]:
    for line in text.splitlines():
        if not (line.startswith("--- ") or line.startswith("+++ ")):
            continue
        raw = line[4:].split("\t", 1)[0].strip()
        if raw == "/dev/null":
            continue
        path = Path(raw)
        if path.is_absolute() or ".." in path.parts:
            return f"patch contains an unsafe path: {raw}"
    return None


@lru_cache(maxsize=1)
def _submission() -> Submission:
    if not PATCH.is_file():
        return Submission(None, f"missing requested patch: {PATCH}")
    try:
        patch_text = PATCH.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return Submission(None, f"patch is unreadable: {exc}")
    if not patch_text.strip() or "@@" not in patch_text:
        return Submission(None, "gsap-fix.patch is not a non-empty unified patch")
    unsafe = _safe_patch_paths(patch_text)
    if unsafe:
        return Submission(None, unsafe)

    attempts: list[str] = []
    for strip in (1, 0, 2):
        destination = Path(tempfile.mkdtemp(prefix=f"gsap-fixed-p{strip}-")) / "project"
        shutil.copytree(DATA_PROJECT, destination)
        result = subprocess.run(
            ["patch", f"-p{strip}", "--batch", "--forward", "--input", str(PATCH)],
            cwd=destination,
            text=True,
            capture_output=True,
        )
        if result.returncode == 0 and (destination / "app.js").is_file():
            syntax = subprocess.run(
                ["node", "--check", str(destination / "app.js")],
                cwd=destination,
                text=True,
                capture_output=True,
            )
            if syntax.returncode != 0:
                return Submission(None, f"patched app.js is invalid JavaScript: {(syntax.stderr or syntax.stdout).strip()[:500]}")
            return Submission(destination, None)
        attempts.append(f"-p{strip}: {(result.stderr or result.stdout).strip()[:220]}")
        shutil.rmtree(destination.parent, ignore_errors=True)
    return Submission(None, "patch does not apply cleanly to the supplied checkout; " + " | ".join(attempts))


def _project_or_skip() -> Path:
    submission = _submission()
    if submission.project is None:
        pytest.skip(f"semantic checks skipped because deliverable integrity failed: {submission.error}")
    return submission.project


@lru_cache(maxsize=None)
def _probe(scenario: str) -> dict:
    project = _project_or_skip()
    result = subprocess.run(
        ["node", str(PROBE), str(project / "app.js"), scenario],
        cwd=project,
        text=True,
        capture_output=True,
        timeout=8,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"runtime probe {scenario!r} did not produce JSON: stdout={result.stdout[:500]!r}, stderr={result.stderr[:500]!r}"
        ) from exc
    assert result.returncode == 0 and payload.get("ok") is True, (
        f"runtime probe {scenario!r} failed: {payload.get('error') or result.stderr}; "
        f"the patched controller cannot satisfy its public integration contract"
    )
    return payload["data"]


def _is_close(value: object, expected: float, tolerance: float = 0.01) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isclose(
        float(value), expected, abs_tol=tolerance
    )


def _drawer_is_open(endpoint: dict) -> bool:
    position_ok = (
        _is_close(endpoint.get("x"), 0)
        or _is_close(endpoint.get("xPercent"), 0)
        or _is_close(endpoint.get("right"), 0)
        or "translatex(0" in str(endpoint.get("transform", "")).lower().replace(" ", "")
    )
    return position_ok and endpoint.get("state") == "open" and endpoint.get("ariaHidden") == "false"


def _drawer_is_closed(endpoint: dict) -> bool:
    transform = str(endpoint.get("transform", "")).lower().replace(" ", "")
    position_ok = (
        _is_close(endpoint.get("x"), 360)
        or _is_close(endpoint.get("xPercent"), 100)
        or _is_close(endpoint.get("right"), -360)
        or "translatex(360px)" in transform
        or "translatex(100%)" in transform
    )
    return position_ok and endpoint.get("state") == "closed" and endpoint.get("ariaHidden") == "true"


def test_deliverables_apply_and_open() -> None:
    """The requested artifacts are usable before semantic checks run."""
    submission = _submission()
    assert submission.project is not None, submission.error
    assert REPORT.is_file(), "missing requested performance-review.md"
    try:
        review = REPORT.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise AssertionError(f"performance-review.md is unreadable: {exc}") from exc
    assert len(review.split()) >= 45, "performance-review.md is too sparse to serve as the requested engineering handoff"


def test_interaction_contract_and_reduced_motion() -> None:
    """Visual endpoints, public behavior, and reduced-motion remain correct."""
    data = _probe("behavior")
    assert data["initialRevealedCount"] == 16, (
        f"mount revealed {data['initialRevealedCount']} cards, expected the 16 cards intersecting the fixture viewport"
    )
    initial = data["initialCard"]
    assert _is_close(initial.get("y"), 0) and _is_close(initial.get("opacity"), 1), (
        f"card reveal does not end at the documented authored position and opacity: {initial}"
    )
    assert _drawer_is_open(data["open"]), f"drawer open endpoint or accessibility state changed: {data['open']}"
    assert _drawer_is_closed(data["closed"]), f"drawer closed endpoint or accessibility state changed: {data['closed']}"
    assert not data["reducedNonZeroDurations"], (
        "reduced-motion still uses nonzero animation durations: " + json.dumps(data["reducedNonZeroDurations"][:5])
    )
    assert data["reducedOpenState"] == "closed" and data["reducedAriaHidden"] == "true", (
        "reduced-motion changed the usable closed drawer state"
    )


def test_hot_paths_avoid_layout_churn_and_tween_fanout() -> None:
    """Pointer and list hot paths remain smooth without changing their results."""
    pointer = _probe("pointer")
    reveal = _probe("reveal")
    behavior = _probe("behavior")

    assert pointer["allocationDelta"] <= 3, (
        f"181 pointer events allocated {pointer['allocationDelta']} tweens; repeated allocation recreates the reported hot-path jank"
    )
    assert _is_close(pointer["finalX"], 499) and _is_close(pointer["finalY"], 299), (
        f"halo does not finish at the latest board-relative pointer position: x={pointer['finalX']}, y={pointer['finalY']}"
    )
    has_response = any(
        _is_close(record.get("vars", {}).get("duration"), 0.18)
        and str(record.get("vars", {}).get("ease", "")).lower().replace(" ", "") in {"power3.out", "power3"}
        for record in pointer["records"]
    )
    assert has_response, "pointer optimization lost the documented 0.18-second power3 response"

    assert reveal["firstAllocationDelta"] <= 3, (
        f"one reveal set allocated {reveal['firstAllocationDelta']} tweens instead of bounded batched work"
    )
    assert reveal["repeatAllocationDelta"] == 0, "already revealed cards allocate animation work again on the next scroll"
    assert reveal["forcedLayouts"] <= 1, (
        f"reveal processing caused {reveal['forcedLayouts']} read-after-write layout flushes; measurements and mutations remain interleaved"
    )
    expected_new = {f"card-{index:03d}" for index in range(17, 39)}
    assert expected_new <= set(reveal["revealed"]), "not every newly visible card is revealed"
    assert reveal["card039Revealed"] is False, "an off-screen card was animated despite the documented visible-only behavior"
    card = reveal["card018"]
    assert _is_close(card.get("y"), 0) and _is_close(card.get("opacity"), 1), (
        f"batched card animation changed its visual endpoint: {card}"
    )

    violations = pointer["badLayoutRecords"] + reveal["badLayoutRecords"] + behavior["normalBadLayoutRecords"]
    assert not violations, (
        "GSAP still animates layout-changing properties in the exercised interactions: " + json.dumps(violations[:8])
    )


def test_resize_burst_and_cleanup_are_bounded() -> None:
    """Resize refresh and teardown do not leave repeated or stray work."""
    data = _probe("lifecycle")
    assert 1 <= data["refreshesAfterBurst"] <= 2, (
        f"14-event resize burst produced {data['refreshesAfterBurst']} refresh calls; it must refresh eventually without running per raw event"
    )
    assert data["refreshesAfterCleanup"] == 0, "a pending or newly dispatched resize refreshed ScrollTrigger after cleanup"
    assert data["allocationDeltaAfterCleanup"] == 0 and data["recordDeltaAfterCleanup"] == 0, (
        "controller events still create or update GSAP work after cleanup"
    )
    assert data["haloUnchanged"] and data["drawerUnchanged"], "pointer or drawer state still changes after cleanup"
    assert data["killSignals"] >= 1, "cleanup did not stop controller-owned animation activity"
