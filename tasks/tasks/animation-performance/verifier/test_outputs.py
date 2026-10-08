from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Optional


ROOT = Path(os.environ.get("TASK_ROOT", "/root"))
DATA_PROJECT = ROOT / "data" / "project"
PATCH = ROOT / "results" / "animation-fix.patch"
REPORT = ROOT / "results" / "animation-review.md"

FORBIDDEN_LAYOUT_PROPERTIES = {
    "top",
    "right",
    "bottom",
    "left",
    "inset",
    "inset-block",
    "inset-inline",
    "width",
    "min-width",
    "max-width",
    "height",
    "min-height",
    "max-height",
    "margin",
    "margin-top",
    "margin-right",
    "margin-bottom",
    "margin-left",
    "padding",
    "padding-top",
    "padding-right",
    "padding-bottom",
    "padding-left",
    "border-width",
    "font-size",
    "line-height",
    "flex-basis",
    "gap",
}


@dataclass(frozen=True)
class Rule:
    selector: str
    declarations: dict[str, str]
    media: tuple[str, ...]
    order: int


@dataclass(frozen=True)
class ParsedCSS:
    rules: tuple[Rule, ...]
    keyframes: dict[str, tuple[dict[str, str], ...]]


@dataclass(frozen=True)
class Submission:
    project: Optional[Path]
    error: Optional[str]


def _without_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _blocks(text: str) -> list[tuple[str, str]]:
    """Return top-level (prelude, body) blocks while respecting strings."""
    blocks: list[tuple[str, str]] = []
    start = 0
    index = 0
    while index < len(text):
        if text[index] in "\"'":
            quote = text[index]
            index += 1
            while index < len(text):
                if text[index] == "\\":
                    index += 2
                elif text[index] == quote:
                    index += 1
                    break
                else:
                    index += 1
            continue
        if text[index] != "{":
            index += 1
            continue
        prelude = text[start:index].strip()
        depth = 1
        body_start = index + 1
        index += 1
        while index < len(text) and depth:
            if text[index] in "\"'":
                quote = text[index]
                index += 1
                while index < len(text):
                    if text[index] == "\\":
                        index += 2
                    elif text[index] == quote:
                        index += 1
                        break
                    else:
                        index += 1
                continue
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
            index += 1
        if depth:
            raise ValueError(f"unclosed CSS block beginning with {prelude!r}")
        blocks.append((prelude, text[body_start:index - 1]))
        start = index
    return blocks


def _split_top_level(value: str, delimiter: str = ",") -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    quote: Optional[str] = None
    for index, char in enumerate(value):
        if quote:
            if char == quote and (index == 0 or value[index - 1] != "\\"):
                quote = None
        elif char in "\"'":
            quote = char
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth = max(0, depth - 1)
        elif char == delimiter and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    parts.append(value[start:].strip())
    return [part for part in parts if part]


def _declarations(body: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for declaration in _split_top_level(body, ";"):
        if ":" not in declaration:
            continue
        name, value = declaration.split(":", 1)
        name = name.strip().lower()
        if name:
            result[name] = value.strip().replace("!important", "").strip()
    return result


def _selector_key(selector: str) -> str:
    compact = re.sub(r"\s+", " ", selector.strip().lower())
    compact = re.sub(
        r"\[([\w-]+)\s*=\s*[\"']?([^\"'\]]+)[\"']?\]",
        lambda match: f"[{match.group(1)}={match.group(2).strip()}]",
        compact,
    )
    compact = re.sub(r"\s*([>+~])\s*", r"\1", compact)
    return compact


def _parse_css(text: str) -> ParsedCSS:
    rules: list[Rule] = []
    keyframes: dict[str, tuple[dict[str, str], ...]] = {}
    order = 0

    def visit(source: str, media: tuple[str, ...]) -> None:
        nonlocal order
        for prelude, body in _blocks(source):
            lowered = prelude.strip().lower()
            if lowered.startswith("@media"):
                visit(body, media + (lowered,))
            elif re.match(r"@(?:-\w+-)?keyframes\b", lowered):
                name = lowered.split()[-1]
                keyframes[name] = tuple(_declarations(frame) for _, frame in _blocks(body))
            elif lowered.startswith("@"):
                continue
            else:
                declarations = _declarations(body)
                for selector in _split_top_level(prelude):
                    rules.append(Rule(_selector_key(selector), declarations, media, order))
                order += 1

    visit(_without_comments(text), ())
    return ParsedCSS(tuple(rules), keyframes)


def _merge_parsed(parts: list[ParsedCSS]) -> ParsedCSS:
    rules: list[Rule] = []
    keyframes: dict[str, tuple[dict[str, str], ...]] = {}
    order = 0
    for part in parts:
        for rule in part.rules:
            rules.append(Rule(rule.selector, rule.declarations, rule.media, order))
            order += 1
        keyframes.update(part.keyframes)
    return ParsedCSS(tuple(rules), keyframes)


def _media_matches(media: tuple[str, ...], width: float, reduced: bool) -> bool:
    for query in media:
        if "prefers-reduced-motion" in query and ("reduce" in query) != reduced:
            return False
        maximum = re.search(r"max-width\s*:\s*([0-9.]+)px", query)
        minimum = re.search(r"min-width\s*:\s*([0-9.]+)px", query)
        if maximum and width > float(maximum.group(1)):
            return False
        if minimum and width < float(minimum.group(1)):
            return False
    return True


def _specificity(selector: str) -> tuple[int, int, int]:
    ids = selector.count("#")
    classes_and_attrs = selector.count(".") + selector.count("[") + selector.count(":")
    stripped = re.sub(r"[#.][\w-]+|\[[^]]+\]|:{1,2}[\w()-]+|[>+~*]", " ", selector)
    elements = len(re.findall(r"\b[a-z][\w-]*\b", stripped))
    return ids, classes_and_attrs, elements


def _style(parsed: ParsedCSS, selectors: list[str], width: float, reduced: bool = False) -> dict[str, str]:
    accepted = {_selector_key(selector) for selector in selectors}
    winners: dict[str, tuple[tuple[int, int, int], int, str]] = {}
    for rule in parsed.rules:
        if rule.selector not in accepted or not _media_matches(rule.media, width, reduced):
            continue
        specificity = _specificity(rule.selector)
        for name, value in rule.declarations.items():
            candidate = (specificity, rule.order, value)
            if name not in winners or candidate[:2] >= winners[name][:2]:
                winners[name] = candidate
    return {name: row[2] for name, row in winners.items()}


def _transition_properties(declarations: dict[str, str]) -> set[str]:
    if "transition-property" in declarations:
        return {part.strip().lower() for part in _split_top_level(declarations["transition-property"])}
    shorthand = declarations.get("transition", "")
    if not shorthand or shorthand.strip().lower() == "none":
        return set()
    properties: set[str] = set()
    ignored = {
        "ease",
        "linear",
        "ease-in",
        "ease-out",
        "ease-in-out",
        "step-start",
        "step-end",
        "normal",
        "allow-discrete",
    }
    for item in _split_top_level(shorthand):
        tokens = re.findall(r"(?:cubic-bezier|steps|linear)\([^)]*\)|[^\s]+", item.lower())
        prop = "all"
        for token in tokens:
            if re.fullmatch(r"-?(?:\d*\.)?\d+m?s", token) or token in ignored or "(" in token:
                continue
            prop = token
            break
        if prop != "none":
            properties.add(prop)
    return properties


def _duration_is_effectively_zero(value: str) -> bool:
    durations = re.findall(r"([0-9.]+)\s*(ms|s)\b", value.lower())
    if not durations:
        return False
    milliseconds = [float(number) * (1000 if unit == "s" else 1) for number, unit in durations]
    return max(milliseconds) <= 1.0


def _motion_disabled(style: dict[str, str], kind: str) -> bool:
    shorthand = style.get(kind, "").strip().lower()
    if shorthand == "none" or shorthand.startswith("none "):
        return True
    return _duration_is_effectively_zero(style.get(f"{kind}-duration", ""))


def _length(value: str, *, axis_size: float, viewport_width: float) -> float:
    token = value.strip().lower()
    if token in {"0", "+0", "-0", "0px", "0%"}:
        return 0.0
    match = re.fullmatch(r"(-?(?:\d*\.)?\d+)\s*(px|%|vw)", token)
    if not match:
        raise ValueError(f"unsupported transform length {value!r}")
    number = float(match.group(1))
    if match.group(2) == "px":
        return number
    if match.group(2) == "%":
        return axis_size * number / 100
    return viewport_width * number / 100


def _transform(value: str, *, width: float, height: float, viewport_width: float) -> tuple[float, float, float, float]:
    value = value.strip().lower()
    if not value or value == "none":
        return 0.0, 0.0, 1.0, 1.0
    tx = ty = 0.0
    sx = sy = 1.0
    functions = re.findall(r"([a-z0-9]+)\(([^)]*)\)", value)
    if not functions:
        raise ValueError(f"unsupported transform {value!r}")
    for name, raw_args in functions:
        args = [arg.strip() for arg in _split_top_level(raw_args)]
        if len(args) == 1 and " " in args[0].strip():
            args = args[0].split()
        if name == "translatex":
            tx += _length(args[0], axis_size=width, viewport_width=viewport_width)
        elif name == "translatey":
            ty += _length(args[0], axis_size=height, viewport_width=viewport_width)
        elif name in {"translate", "translate3d"}:
            tx += _length(args[0], axis_size=width, viewport_width=viewport_width)
            if len(args) > 1:
                ty += _length(args[1], axis_size=height, viewport_width=viewport_width)
        elif name == "scalex":
            sx *= float(args[0])
        elif name == "scaley":
            sy *= float(args[0])
        elif name == "scale":
            sx *= float(args[0])
            sy *= float(args[1] if len(args) > 1 else args[0])
        elif name == "scale3d":
            sx *= float(args[0])
            sy *= float(args[1])
        elif name == "matrix" and len(args) == 6:
            sx *= float(args[0])
            sy *= float(args[3])
            tx += float(args[4])
            ty += float(args[5])
        else:
            raise ValueError(f"unsupported transform function {name!r}")
    return tx, ty, sx, sy


def _css_width(value: str, viewport_width: float, parent_width: Optional[float] = None) -> float:
    token = value.strip().lower()
    if token.endswith("px"):
        return float(token[:-2])
    if token.endswith("vw"):
        return viewport_width * float(token[:-2]) / 100
    if token.endswith("%") and parent_width is not None:
        return parent_width * float(token[:-1]) / 100
    raise ValueError(f"unsupported width {value!r}")


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
        return Submission(None, "animation-fix.patch is not a non-empty unified patch")
    unsafe = _safe_patch_paths(patch_text)
    if unsafe:
        return Submission(None, unsafe)
    attempts: list[str] = []
    for strip in (1, 0, 2):
        destination = Path(tempfile.mkdtemp(prefix=f"animation-fixed-p{strip}-")) / "project"
        shutil.copytree(DATA_PROJECT, destination)
        result = subprocess.run(
            ["patch", f"-p{strip}", "--batch", "--forward", "--input", str(PATCH)],
            cwd=destination,
            text=True,
            capture_output=True,
        )
        if result.returncode == 0 and (destination / "styles" / "components.css").is_file():
            return Submission(destination, None)
        attempts.append(f"-p{strip}: {(result.stderr or result.stdout).strip()[:240]}")
        shutil.rmtree(destination.parent, ignore_errors=True)
    return Submission(None, "patch does not apply cleanly to the supplied checkout; " + " | ".join(attempts))


def _parsed_submission() -> ParsedCSS:
    submission = _submission()
    assert submission.project is not None, submission.error
    try:
        parts = [_parse_css(path.read_text(encoding="utf-8")) for path in sorted((submission.project / "styles").glob("*.css"))]
        return _merge_parsed(parts)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise AssertionError(f"patched stylesheets are not readable CSS: {exc}") from exc


def _close(actual: float, expected: float, label: str, tolerance: float = 0.15) -> None:
    assert math.isclose(actual, expected, abs_tol=tolerance), f"{label} is {actual:g}, expected {expected:g}"


def test_deliverables_apply_and_open() -> None:
    submission = _submission()
    assert submission.project is not None, submission.error
    assert REPORT.is_file(), "missing requested animation-review.md"
    try:
        review = REPORT.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise AssertionError(f"animation-review.md is unreadable: {exc}") from exc
    assert len(review.split()) >= 35, "animation-review.md is too sparse to hand off the requested review"


def test_motion_uses_non_layout_properties_without_removing_safe_effects() -> None:
    parsed = _parsed_submission()
    violations: list[str] = []
    for rule in parsed.rules:
        properties = _transition_properties(rule.declarations)
        bad = properties & FORBIDDEN_LAYOUT_PROPERTIES
        if "all" in properties:
            bad.add("all")
        if bad:
            violations.append(f"{rule.selector} transitions {sorted(bad)}")
    for name, frames in parsed.keyframes.items():
        bad = set().union(*(set(frame) & FORBIDDEN_LAYOUT_PROPERTIES for frame in frames))
        if bad:
            violations.append(f"@keyframes {name} animates {sorted(bad)}")
    assert not violations, "layout-triggering motion remains: " + "; ".join(violations)

    for selector in (".side-panel", ".dialog", ".toast", ".progress__fill"):
        style = _style(parsed, [selector], 1280)
        assert "transform" in _transition_properties(style), f"{selector} no longer has visible transform motion"

    brand = _style(parsed, [".brand-mark", ".brand-mark:hover"], 1280)
    button = _style(parsed, [".safe-button", ".safe-button:hover"], 1280)
    card = _style(parsed, [".dialog__card"], 1280)
    assert {"transform", "opacity"} <= _transition_properties(brand), "the safe brand-mark effect was removed"
    assert {"transform", "opacity"} <= _transition_properties(button), "the safe button effect was removed"
    assert "transform" in _transition_properties(card), "the safe dialog-card scale effect was removed"
    pulse = parsed.keyframes.get("live-pulse", ())
    pulse_properties = set().union(*(set(frame) for frame in pulse)) if pulse else set()
    assert {"transform", "opacity"} <= pulse_properties, "the safe live-pulse animation was removed or degraded"


def test_responsive_interaction_endpoints_are_preserved() -> None:
    parsed = _parsed_submission()
    for viewport, expected_panel_width, toast_bottom, toast_hidden_y in (
        (1280.0, 288.0, 20.0, 28.0),
        (390.0, 327.6, 12.0, 16.0),
    ):
        panel_base = _style(parsed, [".side-panel"], viewport)
        panel_width = _css_width(panel_base.get("width", ""), viewport)
        _close(panel_width, expected_panel_width, f"side-panel width at {viewport:g}px")
        closed = _style(parsed, [".side-panel", '.side-panel[data-state="closed"]'], viewport)
        opened = _style(parsed, [".side-panel", '.side-panel[data-state="open"]'], viewport)
        closed_transform = _transform(closed.get("transform", "none"), width=panel_width, height=180, viewport_width=viewport)
        open_transform = _transform(opened.get("transform", "none"), width=panel_width, height=180, viewport_width=viewport)
        _close(closed_transform[0], -panel_width, f"closed side-panel x endpoint at {viewport:g}px")
        _close(open_transform[0], 0, f"open side-panel x endpoint at {viewport:g}px")
        _close(float(closed.get("opacity", "1")), 0, "closed side-panel opacity")
        _close(float(opened.get("opacity", "0")), 1, "open side-panel opacity")

        dialog_hidden = _style(parsed, [".dialog"], viewport)
        dialog_visible = _style(parsed, [".dialog", '.dialog[data-state="visible"]'], viewport)
        hidden_transform = _transform(dialog_hidden.get("transform", "none"), width=600, height=210, viewport_width=viewport)
        visible_transform = _transform(dialog_visible.get("transform", "none"), width=600, height=210, viewport_width=viewport)
        _close(float(dialog_hidden.get("top", "0").removesuffix("px")), 0, "dialog layout top anchor")
        _close(hidden_transform[1], 18, "hidden dialog y endpoint")
        _close(visible_transform[1], 0, "visible dialog y endpoint")
        assert dialog_hidden.get("pointer-events") == "none", "hidden dialog became interactive"
        assert dialog_visible.get("pointer-events") == "auto", "visible dialog is not interactive"

        toast_hidden = _style(parsed, [".toast"], viewport)
        toast_visible = _style(parsed, [".toast", '.toast[data-state="visible"]'], viewport)
        _close(float(toast_hidden.get("bottom", "0").removesuffix("px")), toast_bottom, f"toast anchor at {viewport:g}px")
        hidden_cue = _transform(toast_hidden.get("transform", "none"), width=360, height=60, viewport_width=viewport)
        visible_cue = _transform(toast_visible.get("transform", "none"), width=360, height=60, viewport_width=viewport)
        _close(hidden_cue[1], toast_hidden_y, f"hidden toast y endpoint at {viewport:g}px")
        _close(hidden_cue[2], .98, f"hidden toast scale at {viewport:g}px", .005)
        _close(visible_cue[1], 0, f"visible toast y endpoint at {viewport:g}px")
        _close(visible_cue[2], 1, f"visible toast scale at {viewport:g}px", .005)

    track = _style(parsed, [".progress"], 1280)
    fill_base = _style(parsed, [".progress__fill"], 1280)
    track_width = _css_width(track.get("width", ""), 1280)
    fill_width = _css_width(fill_base.get("width", ""), 1280, track_width)
    _close(fill_width, track_width, "progress fill layout width")
    origin = fill_base.get("transform-origin", "").lower()
    assert origin.startswith("left") or origin.startswith("0"), "progress transform must grow from the left edge"
    for state, expected_fraction in (("empty", 0.0), ("half", .5), ("complete", 1.0)):
        selectors = [".progress__fill"]
        if state != "empty":
            selectors.append(f'.progress[data-progress="{state}"] .progress__fill')
        transform = _transform(_style(parsed, selectors, 1280).get("transform", "none"), width=track_width, height=10, viewport_width=1280)
        _close(transform[2], expected_fraction, f"{state} progress fraction", .005)

    badge_frames = parsed.keyframes.get("badge-bounce", ())
    badge_offsets = []
    for frame in badge_frames:
        if "transform" in frame:
            badge_offsets.append(_transform(frame["transform"], width=100, height=28, viewport_width=1280)[1])
    assert any(math.isclose(offset, -6, abs_tol=.15) for offset in badge_offsets), "status badge lost its -6px attention peak"
    assert any(math.isclose(offset, 0, abs_tol=.15) for offset in badge_offsets), "status badge no longer returns to its resting position"


def test_reduced_motion_disables_motion_without_changing_states() -> None:
    parsed = _parsed_submission()
    for selector, kind in (
        (".side-panel", "transition"),
        (".dialog", "transition"),
        (".dialog__card", "transition"),
        (".toast", "transition"),
        (".progress__fill", "transition"),
        (".brand-mark", "transition"),
        (".safe-button", "transition"),
        (".status-badge", "animation"),
        (".live-dot", "animation"),
    ):
        reduced_style = _style(parsed, [selector], 390, reduced=True)
        assert _motion_disabled(reduced_style, kind), f"{selector} still has nonessential {kind} motion in reduced-motion mode"

    state_selector_sets = (
        [".side-panel", '.side-panel[data-state="closed"]'],
        [".side-panel", '.side-panel[data-state="open"]'],
        [".dialog", '.dialog[data-state="visible"]'],
        [".toast", '.toast[data-state="visible"]'],
        [".progress__fill", '.progress[data-progress="half"] .progress__fill'],
    )
    for selectors in state_selector_sets:
        normal = _style(parsed, list(selectors), 390, reduced=False)
        reduced = _style(parsed, list(selectors), 390, reduced=True)
        for property_name in ("transform", "opacity", "pointer-events", "width", "bottom", "top"):
            if property_name in normal:
                assert reduced.get(property_name) == normal[property_name], (
                    f"reduced-motion changes the {property_name} endpoint for {selectors[-1]}"
                )
