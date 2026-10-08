from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


RESULTS_ROOT = Path(os.environ.get("SKILLSBENCH_RESULTS_ROOT", "/root/results"))
DATA_ROOT = Path(os.environ.get("SKILLSBENCH_DATA_ROOT", "/root/data"))
PROJECT = RESULTS_ROOT / "field-notes-app"
SOURCE_PROJECT = DATA_ROOT / "field-notes-app"
REQUIRED_TABS = {"index", "saved", "search"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _compact(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.S)
    source = re.sub(r"(^|\s)//[^\n]*", r"\1 ", source)
    return re.sub(r"\s+", " ", source).strip()


def _route_sources() -> list[Path]:
    app = PROJECT / "app"
    return sorted(path for path in app.rglob("*.tsx") if path.is_file()) if app.is_dir() else []


def _array_group() -> Path | None:
    app = PROJECT / "app"
    if not app.is_dir():
        return None
    for path in sorted(item for item in app.rglob("*") if item.is_dir()):
        match = re.fullmatch(r"\(([^()]+)\)", path.name)
        if not match or "," not in match.group(1):
            continue
        members = {item.strip() for item in match.group(1).split(",")}
        if members == REQUIRED_TABS:
            return path
    return None


def _resolve_local_import(origin: Path, specifier: str) -> Path | None:
    if specifier.startswith("@/"):
        base = PROJECT / specifier[2:]
    elif specifier.startswith("."):
        base = origin.parent / specifier
    else:
        return None
    candidates = [base, base.with_suffix(".ts"), base.with_suffix(".tsx"), base / "index.ts", base / "index.tsx"]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _reachable_paths(entry: Path) -> list[Path]:
    pending = [entry]
    seen: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in seen or not path.is_file() or PROJECT not in path.parents:
            continue
        seen.add(path)
        source = _read(path)
        for specifier in re.findall(r"\bfrom\s*['\"]([^'\"]+)['\"]", source):
            resolved = _resolve_local_import(path, specifier)
            if resolved is not None:
                pending.append(resolved)
    return sorted(seen)


def _reachable_sources(entry: Path) -> str:
    return "\n".join(_read(path) for path in _reachable_paths(entry))


def _trigger_entries(source: str) -> list[tuple[str, str, str]]:
    entries: list[tuple[int, str, str, str]] = []
    paired = re.compile(
        r"<NativeTabs\.Trigger\b(?P<attrs>[^>]*)>(?P<body>.*?)</NativeTabs\.Trigger\s*>",
        re.S,
    )
    occupied: list[tuple[int, int]] = []
    for match in paired.finditer(source):
        name_match = re.search(r"\bname\s*=\s*['\"]([^'\"]+)['\"]", match.group("attrs"))
        if name_match:
            entries.append((match.start(), name_match.group(1), match.group("attrs"), match.group("body")))
            occupied.append(match.span())
    self_closing = re.compile(r"<NativeTabs\.Trigger\b(?P<attrs>[^>]*)/>", re.S)
    for match in self_closing.finditer(source):
        if any(start <= match.start() < end for start, end in occupied):
            continue
        name_match = re.search(r"\bname\s*=\s*['\"]([^'\"]+)['\"]", match.group("attrs"))
        if name_match:
            entries.append((match.start(), name_match.group(1), match.group("attrs"), ""))
    return [(name, attrs, body) for _, name, attrs, body in sorted(entries)]


def _normalized_trigger_name(name: str) -> str:
    return name.strip().strip("()")


def test_project_is_complete_and_preserves_fixture() -> None:
    assert PROJECT.is_dir(), f"updated project is missing at {PROJECT}"
    required = [
        "package.json",
        "app.json",
        "tsconfig.json",
        "README.md",
        "data/notes.json",
        "lib/notes.ts",
        "components/note-list.tsx",
        "components/note-card.tsx",
        "scripts/validate-data.py",
    ]
    missing = [relative for relative in required if not (PROJECT / relative).is_file()]
    assert not missing, "the delivered project is incomplete: " + ", ".join(missing)

    package = json.loads(_read(PROJECT / "package.json"))
    dependencies = package.get("dependencies", {})
    assert str(dependencies.get("expo", "")).lstrip("~^").startswith("55."), (
        "the delivered package no longer targets Expo SDK 55"
    )
    assert "expo-router" in dependencies, "the delivered package removed expo-router"
    tsconfig = _read(PROJECT / "tsconfig.json")
    assert '"@/*"' in tsconfig and '"./*"' in tsconfig, "the project path alias was not preserved"

    expected_notes = json.loads(_read(SOURCE_PROJECT / "data" / "notes.json"))
    actual_notes = json.loads(_read(PROJECT / "data" / "notes.json"))
    assert actual_notes == expected_notes, "the refactor changed the frozen note records or saved flags"
    assert len(actual_notes) == 24 and len({row["id"] for row in actual_notes}) == 24

    validation = subprocess.run(
        ["python3", "scripts/validate-data.py"],
        cwd=PROJECT,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert validation.returncode == 0, "the project's local data validation fails:\n" + validation.stdout + validation.stderr


def test_native_tabs_cover_required_destinations() -> None:
    root_layout = PROJECT / "app" / "_layout.tsx"
    assert root_layout.is_file(), "the root route layout is missing"
    source = _compact(_read(root_layout))
    assert "expo-router/unstable-native-tabs" in source, "the root layout does not import Expo Router NativeTabs"
    assert re.search(r"<NativeTabs(?:\s|>)", source), "the root navigator is not NativeTabs"
    assert not re.search(r"\bimport\s*{[^}]*\bTabs\b[^}]*}\s*from\s*['\"]expo-router['\"]", source), (
        "the legacy JavaScript Tabs import remains in the root navigator"
    )

    entries = _trigger_entries(source)
    names = [_normalized_trigger_name(name) for name, _, _ in entries]
    assert len(entries) == 3 and set(names) == REQUIRED_TABS, (
        f"NativeTabs must have exactly the Home, Saved, and Search route triggers; observed {names}"
    )
    assert names[-1] == "search", "the native Search tab must be last so it integrates with the tab bar"
    search_entry = entries[names.index("search")]
    assert re.search(r"\brole\s*=\s*['\"]search['\"]", search_entry[1]), (
        "the Search trigger is missing its native search role"
    )
    labels = " ".join(body for _, _, body in entries).lower()
    assert "home" in labels and "saved" in labels, "Home and Saved triggers need visible native labels"

    all_route_source = _compact("\n".join(_read(path) for path in _route_sources()))
    assert not re.search(r"<Tabs(?:\.|\s|>)", all_route_source), "a legacy JavaScript Tabs navigator remains in app/"
    assert not (PROJECT / "app" / "(tabs)").exists(), "the obsolete (tabs) route group was not removed"


def test_shared_tab_stacks_and_stable_public_routes() -> None:
    group = _array_group()
    assert group is not None, (
        "Home, Saved, and Search are not represented by one shared Expo Router array group"
    )
    required_routes = ["index.tsx", "saved.tsx", "search.tsx", "notes/[id].tsx", "_layout.tsx"]
    missing = [relative for relative in required_routes if not (group / relative).is_file()]
    assert not missing, "the shared tab stack is missing route files: " + ", ".join(missing)

    layout = _compact(_read(group / "_layout.tsx"))
    assert "expo-router/stack" in layout or re.search(r"\bStack\b.*?from\s*['\"]expo-router['\"]", layout), (
        "the shared tab layout does not use an Expo Router Stack"
    )
    assert re.search(r"<Stack(?:\s|>)", layout), "the array route layout does not render a Stack"
    for anchor in REQUIRED_TABS:
        pattern = rf"\b{anchor}\s*:\s*{{\s*anchor\s*:\s*['\"]{anchor}['\"]"
        assert re.search(pattern, layout), f"the {anchor} tab does not anchor its own stack history"
    assert re.search(r"<Stack\.Screen\b[^>]*\bname\s*=\s*['\"]notes/\[id\]['\"]", layout), (
        "the dynamic note-detail route is not registered in the shared tab Stack"
    )

    assert not (PROJECT / "app" / "notes" / "[id].tsx").exists(), (
        "the old root-level detail route remains alongside the shared implementation"
    )
    route_sources = _route_sources()
    detail_routes = [path for path in route_sources if path.parts[-2:] == ("notes", "[id].tsx")]
    assert detail_routes == [group / "notes" / "[id].tsx"], (
        "there must be one shared dynamic note-detail source, not duplicated per tab"
    )
    missing_default_exports = [
        str(path.relative_to(PROJECT))
        for path in route_sources
        if "export default" not in _compact(_read(path))
    ]
    assert not missing_default_exports, "route files without a default screen export: " + ", ".join(missing_default_exports)


def test_native_header_search_preserves_filter_contract() -> None:
    group = _array_group()
    assert group is not None, "the shared tab route group is unavailable"
    search_screen = group / "search.tsx"
    assert search_screen.is_file(), "the Search route is missing"
    reachable_paths = _reachable_paths(search_screen)
    reachable_chunks = [_compact(_read(path)) for path in reachable_paths]
    reachable = "\n".join(reachable_chunks)
    lowered = reachable.lower()

    has_header_search = "headersearchbaroptions" in lowered or re.search(r"<Stack\.SearchBar(?:\s|/|>)", reachable)
    assert has_header_search, "Search does not expose its input through the native stack header"
    assert "onchangetext" in lowered, "the native search field is not connected to filtering state"
    assert "textinput" not in lowered, "the legacy in-page TextInput remains reachable from Search"

    normalization_pattern = re.compile(
        r"(?:\.trim\(\).{0,240}\.(?:tolowercase|tolocalelowercase)\(|"
        r"\.(?:tolowercase|tolocalelowercase)\(\).{0,240}\.trim\()",
        re.I,
    )
    assert any(normalization_pattern.search(chunk) for chunk in reachable_chunks), (
        "search no longer combines whitespace trimming with case normalization"
    )
    assert ".includes(" in lowered, "search no longer performs text containment matching"
    for field in ("title", "body", "author", "tags"):
        assert re.search(rf"\b{field}\b", lowered), f"search no longer considers note {field}"
    assert re.search(r"if\s*\(\s*!\s*query\s*\)\s*return\s+notes", reachable, flags=re.I), (
        "an empty normalized query no longer returns the complete note list"
    )
    assert "no notes" in lowered and ("query" in lowered or "search" in lowered), (
        "Search has no query-aware empty-result state"
    )
