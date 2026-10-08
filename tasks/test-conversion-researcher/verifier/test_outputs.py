from __future__ import annotations

import os
from pathlib import Path
import re


RESULTS = Path(os.environ.get("RESULTS_DIR", "/root/results"))
PLAN = RESULTS / "conversion_plan.md"


def _read_plan() -> str:
    if not PLAN.is_file():
        return ""
    try:
        return PLAN.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def _normalize(text: str) -> str:
    text = text.casefold().replace("_", " ").replace("`", "")
    return re.sub(r"\s+", " ", text)


MOVE_RE = re.compile(r"\b(?:move|moves|moved|moving|migrate|migrates|migrated|migrating|convert|converts|converted|converting)\b|\bbrowser[ -]test")
KEEP_RE = re.compile(r"\b(?:keep|keeps|kept|keeping|retain|retains|retained|retaining|remain|remains|remaining|leave|leaves|left|stay|stays|stayed)\b|\bunit[ -](?:only|test)|\bdo not (?:move|migrate|convert)\b")


def _anchor_segments(text: str, anchors: tuple[str, ...]) -> list[tuple[str, int]]:
    # Prefer a physical row/bullet, but also accept an ordinary prose paragraph
    # where a line wrap separates the test name from its disposition.
    raw_segments = text.splitlines()
    raw_segments += re.split(r"\n\s*\n", text)
    found: list[tuple[str, int]] = []
    for raw in raw_segments:
        segment = _normalize(raw)
        for anchor in anchors:
            needle = _normalize(anchor)
            start = 0
            while True:
                pos = segment.find(needle, start)
                if pos < 0:
                    break
                found.append((segment, pos + len(needle) // 2))
                start = pos + len(needle)
    return found


def _nearest_action(regex: re.Pattern[str], segment: str, anchor_center: int) -> int | None:
    distances = [abs((match.start() + match.end()) // 2 - anchor_center) for match in regex.finditer(segment)]
    return min(distances) if distances else None


def _matches_disposition(text: str, anchors: tuple[str, ...], expected: str) -> bool:
    action_re = MOVE_RE if expected == "move" else KEEP_RE
    contrary_re = KEEP_RE if expected == "move" else MOVE_RE
    for segment, anchor_center in _anchor_segments(text, anchors):
        expected_distance = _nearest_action(action_re, segment, anchor_center)
        contrary_distance = _nearest_action(contrary_re, segment, anchor_center)
        if expected_distance is not None and (
            contrary_distance is None or expected_distance <= contrary_distance
        ):
            return True
    return False


def test_scope_dispositions():
    text = _read_plan()
    assert text, "scope cannot be assessed because conversion_plan.md is missing or unreadable"

    cases = [
        (
            "move OpensBookmarksAndReportsProcess",
            ("SidePanelServiceTest.OpensBookmarksAndReportsProcess", "OpensBookmarksAndReportsProcess"),
            "move",
        ),
        (
            "keep RejectsEmptyUrlWithoutBrowser",
            ("SidePanelServiceGuardTest.RejectsEmptyUrlWithoutBrowser", "RejectsEmptyUrlWithoutBrowser"),
            "keep",
        ),
        (
            "move both coordinator window tests",
            (
                "tests/unit/side_panel_coordinator_unittest.cc",
                "DetachedWindowIsInitializedAndRegistered",
                "CloseDetachedWindowHidesNativeWindow",
            ),
            "move",
        ),
        (
            "keep URL formatter coverage",
            ("tests/unit/url_formatter_unittest.cc", "UrlFormatterTest", "FormatsEmptyLabel", "PreservesBookmarkLabel"),
            "keep",
        ),
    ]
    missing = [label for label, anchors, expected in cases if not _matches_disposition(text, anchors, expected)]
    assert not missing, "missing or incorrect test dispositions: " + "; ".join(missing)
