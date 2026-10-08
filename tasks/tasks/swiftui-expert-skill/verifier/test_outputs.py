from __future__ import annotations

import json
import os
from pathlib import Path
import re

import pytest


SUBMISSION = Path(os.environ.get("SUBMISSION_ROOT", "/root/results/LoopLog"))
SOURCE_DATA = Path(os.environ.get("DATA_ROOT", "/root/data/LoopLog"))


EXPECTED_COPY = {
    "activity_count": ("%lld activities", "アクティビティ%lld件"),
    "activity_feed": ("Activity Feed", "アクティビティ"),
    "search_activities": ("Search activities", "アクティビティを検索"),
    "favorites_only": ("Favorites only", "お気に入りのみ"),
    "no_matching_activities": ("No matching activities", "一致するアクティビティはありません"),
    "oldest_first": ("Oldest first", "古い順"),
    "newest_first": ("Newest first", "新しい順"),
    "favorite": ("Favorite", "お気に入りに追加"),
    "remove_favorite": ("Remove favorite", "お気に入りから削除"),
    "hike": ("Hike", "ハイキング"),
    "ride": ("Ride", "サイクリング"),
    "run": ("Run", "ランニング"),
    "activity_type": ("Activity type", "アクティビティの種類"),
    "distance": ("Distance", "距離"),
    "date": ("Date", "日付"),
}


def _production_swift_files() -> list[Path]:
    if not SUBMISSION.is_dir():
        return []
    return sorted(
        path
        for path in SUBMISSION.rglob("*.swift")
        if not any(part.lower().endswith("tests") for part in path.parts)
    )


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def _swift_source() -> str:
    return "\n".join(_strip_comments(path.read_text(encoding="utf-8")) for path in _production_swift_files())


def _type_body(source: str, name: str) -> str:
    match = re.search(rf"\b(?:struct|class|final\s+class)\s+{re.escape(name)}\b[^{{]*{{", source)
    if not match:
        return ""
    start = match.end() - 1
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1:index]
    return ""


def _catalog_entries() -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    for path in sorted(SUBMISSION.rglob("*.xcstrings")) if SUBMISSION.is_dir() else []:
        payload = json.loads(path.read_text(encoding="utf-8"))
        strings = payload.get("strings", {})
        if not isinstance(strings, dict):
            continue
        for key, record in strings.items():
            try:
                loc = record["localizations"]
                en = loc["en"]["stringUnit"]["value"]
                ja = loc["ja"]["stringUnit"]["value"]
            except (KeyError, TypeError):
                continue
            if isinstance(key, str) and isinstance(en, str) and isinstance(ja, str):
                entries[key] = (en, ja)
    return entries


def _swift_literals(source: str) -> set[str]:
    raw = set(re.findall(r'"((?:\\.|[^"\\])*)"', source))
    normalized = set(raw)
    for literal in raw:
        placeholder = re.sub(r"\\\([^)]*\)", "%lld", literal)
        normalized.add(placeholder)
    return normalized


def _call_arguments(source: str, marker: str) -> list[str]:
    """Return balanced call bodies so nested modifiers do not confuse regex checks."""
    bodies = []
    cursor = 0
    while True:
        start = source.find(marker, cursor)
        if start < 0:
            return bodies
        opening = start + len(marker) - 1
        depth = 0
        in_string = False
        escaped = False
        for index in range(opening, len(source)):
            char = source[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    bodies.append(source[opening + 1:index])
                    cursor = index + 1
                    break
        else:
            return bodies


def test_artifact_usability():
    assert SUBMISSION.is_dir(), "the requested /root/results/LoopLog project is missing"
    files = _production_swift_files()
    assert files, "the revised project contains no readable production Swift source"
    source = _swift_source()
    for type_name in ("Activity", "ActivityStore", "ActivityFeedView", "ActivityRow", "ActivityDetailView"):
        assert re.search(rf"\b(?:struct|class|final\s+class)\s+{type_name}\b", source), (
            f"essential app type {type_name} is missing, so the replacement project is incomplete"
        )
    catalogs = list(SUBMISSION.rglob("*.xcstrings"))
    assert catalogs, "the English/Japanese string catalog is missing"
    fixture_paths = list(SUBMISSION.rglob("Activities.json"))
    assert fixture_paths, "the bundled 500-item offline fixture is missing"
    rows = json.loads(fixture_paths[0].read_text(encoding="utf-8"))
    assert isinstance(rows, list) and len(rows) == 500, "the regression fixture must retain all 500 activities"
    ids = [row.get("id") for row in rows if isinstance(row, dict)]
    assert len(ids) == 500 and len(set(ids)) == 500, "activity fixture IDs must remain complete and unique"


def test_store_ownership_and_observation():
    source = _swift_source()
    store = _type_body(source, "ActivityStore")
    app = _type_body(source, "LoopLogApp")
    feed = _type_body(source, "ActivityFeedView")
    assert store and re.search(r"@Observable[\s\S]{0,120}(?:final\s+)?class\s+ActivityStore", source), (
        "ActivityStore must retain Observation tracking so synchronized changes refresh the feed"
    )
    assert re.search(r"@MainActor[\s\S]{0,120}(?:final\s+)?class\s+ActivityStore", source), (
        "the UI store must remain main-actor isolated"
    )
    assert re.search(
        r"@State\s+private\s+var\s+\w*store\w*(?:\s*:\s*ActivityStore)?\s*=\s*(?:ActivityStore\.)?preview",
        app,
    ), (
        "LoopLogApp must remain the explicit owner of the preview ActivityStore"
    )
    assert re.search(r"(?:let|var|@Bindable\s+(?:private\s+)?var)\s+store\s*:\s*ActivityStore", feed), (
        "ActivityFeedView must receive the parent's ActivityStore"
    )
    assert not re.search(r"@(?:State|StateObject|ObservedObject)\b[^\n]*\bstore\b", feed), (
        "the injected store is being re-owned by ActivityFeedView, which can ignore replacement input"
    )


def test_local_state_and_passed_values():
    source = _swift_source()
    feed = _type_body(source, "ActivityFeedView")
    row = _type_body(source, "ActivityRow")
    non_private = re.findall(r"@State(?:\([^\n]*\))?\s+(?!private\b)var\s+(\w+)", source)
    assert not non_private, f"view-owned @State must be private; found {sorted(set(non_private))}"
    assert not re.search(r"@(?:State|StateObject)\b[^\n]*\bactivity\b", row), (
        "ActivityRow must render the passed activity rather than freezing its initial value as local state"
    )
    assert re.search(r"\b(?:let|var)\s+activity\s*:\s*Activity\b", row), (
        "ActivityRow no longer exposes the current activity as a passed value"
    )
    assert re.search(r"\.searchable\s*\([^)]*\btext\s*:\s*\$\w+", feed), (
        "the feed must still bind search UI to private local state"
    )
    assert re.search(r"Toggle\s*\([^)]*\bisOn\s*:\s*\$\w+", feed), (
        "the feed must still bind the favorites-only control to private local state"
    )


def test_dynamic_rows_use_activity_identity():
    source = _swift_source()
    feed = _type_body(source, "ActivityFeedView")
    assert not re.search(r"(?:ForEach|List)\s*\([^\n)]*\.indices\b", feed), (
        "dynamic rows still use collection positions, so filtering or insertion can transfer row identity"
    )
    assert not re.search(r"ForEach\s*\([^)]*id\s*:\s*\\\.(?:self|offset)\b", feed), (
        "row identity must come from Activity.id rather than a position or whole mutable value"
    )
    assert re.search(r"(?:ForEach|List)\s*\(\s*[A-Za-z_]\w*\s*\)\s*\{\s*[A-Za-z_]\w*\s+in", feed), (
        "the visible Activity collection must drive the dynamic rows directly"
    )


def test_favorite_action_targets_visible_activity_id():
    source = _swift_source()
    feed = _type_body(source, "ActivityFeedView")
    assert not re.search(r"(?:store\.activities|visible\w*|filtered\w*)\s*\[\s*\w+\s*\]", feed), (
        "favorite behavior still indexes a source or derived array by row position"
    )
    row = re.search(
        r"(?:ForEach|List)\s*\(\s*[A-Za-z_]\w*\s*\)\s*\{\s*([A-Za-z_]\w*)\s+in",
        feed,
    )
    assert row, "the visible collection does not expose an Activity value to each row"
    row_name = re.escape(row.group(1))
    assert re.search(rf"toggleFavorite\s*\(\s*id\s*:\s*{row_name}\.id\s*\)", feed), (
        "the row action must send the visible activity's UUID to ActivityStore.toggleFavorite"
    )


@pytest.mark.parametrize(
    "concepts",
    [
        ("activity_feed", "search_activities", "favorites_only", "no_matching_activities", "activity_count"),
        ("oldest_first", "newest_first", "favorite", "remove_favorite"),
        ("hike", "ride", "run", "activity_type", "distance", "date"),
    ],
)
def test_catalog_concepts_are_complete_and_used(concepts):
    entries = _catalog_entries()
    source = _swift_source()
    literals = _swift_literals(source)
    missing = []
    unused = []
    for concept in concepts:
        expected = EXPECTED_COPY[concept]
        keys = [key for key, pair in entries.items() if pair == expected]
        if not keys:
            missing.append(concept)
        elif not any(key in literals or key.replace(" %lld", "") in source for key in keys):
            unused.append(concept)
    assert not missing, f"catalog lacks complete English/Japanese product copy for {missing}"
    assert not unused, f"the revised SwiftUI source does not use catalog-backed copy for {unused}"


def test_dynamic_values_are_locale_aware():
    source = _swift_source()
    assert "DateFormatter" not in source and ".dateFormat" not in source, (
        "hard-coded date formatting prevents Japanese and other locale conventions from applying"
    )
    assert "String(format:" not in source, (
        "String(format:) leaves distance digits, separators, and units outside locale-aware formatting"
    )
    distance_ok = (
        "UnitLength.kilometers" in source
        and ("format: .measurement" in source or ".formatted(.measurement" in source)
    )
    assert distance_ok, "distance must use a locale-aware Measurement format style"
    date_ok = bool(
        re.search(r"Text\s*\([^)]*startedAt\s*,\s*format\s*:\s*\.dateTime", source)
        or re.search(r"startedAt\.formatted\s*\(", source)
    )
    assert date_ok, "activity dates must use a locale-aware date format style"
    activity = _type_body(source, "Activity")
    assert re.search(r"\bvar\s+title\s*:\s*String\b", activity), (
        "activity titles are user content and must remain plain String data rather than localization keys"
    )


def test_modern_navigation_and_modifiers():
    source = _swift_source()
    obsolete = {
        "NavigationView": r"\bNavigationView\b",
        "navigationBarTitle": r"\.navigationBarTitle\s*\(",
        "foregroundColor": r"\.foregroundColor\s*\(",
        "onTapGesture": r"\.onTapGesture\b",
        "generic accessibility(label:)": r"\.accessibility\s*\(\s*label\s*:",
    }
    found = [label for label, pattern in obsolete.items() if re.search(pattern, source)]
    assert not found, f"edited iOS 17 views retain older SwiftUI forms: {found}"
    assert "NavigationStack" in source and ".navigationTitle(" in source, (
        "the feed/detail flow must use current SwiftUI navigation APIs"
    )


def test_favorite_is_a_button_with_scoped_animation():
    source = _swift_source()
    row = _type_body(source, "ActivityRow")
    assert "Button" in row and "heart.fill" in row, (
        "the heart action must be a semantic Button rather than an image-only tap gesture"
    )
    assert ".accessibilityLabel(" in row, "the favorite button needs a clear VoiceOver label"
    animation_calls = _call_arguments(row, ".animation(")
    scoped = "withAnimation" in row or any("value:" in arguments for arguments in animation_calls)
    assert scoped, "the heart scale animation must be tied specifically to the favorite state change"
    unscoped = [arguments for arguments in _call_arguments(source, ".animation(") if "value:" not in arguments]
    assert not unscoped, "a broad animation without a value can animate unrelated feed updates"
