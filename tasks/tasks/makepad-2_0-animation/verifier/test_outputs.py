from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT = RESULTS_DIR / "ops_status_panel.rs"
SUPPORTED = {
    "View",
    "SolidView",
    "RoundedView",
    "ScrollXView",
    "ScrollYView",
    "ScrollXYView",
    "Button",
    "ButtonFlat",
    "ButtonFlatter",
    "CheckBox",
    "Toggle",
    "RadioButton",
    "LinkLabel",
    "TextInput",
}


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def _balanced(text: str) -> bool:
    pairs = {"}": "{", ")": "(", "]": "["}
    stack: list[str] = []
    quote: str | None = None
    escaped = False
    for char in _strip_comments(text):
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ('"', "'"):
            quote = char
        elif char in "{([":
            stack.append(char)
        elif char in "})]":
            if not stack or stack.pop() != pairs[char]:
                return False
    return not stack and quote is None


def _brace_body(text: str, open_index: int) -> str:
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(open_index, len(text)):
        char = text[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ('"', "'"):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[open_index + 1 : index]
    raise ValueError("unclosed block")


def _definition(text: str, name: str) -> tuple[str, str]:
    pattern = re.compile(
        rf"\b(?:let\s+)?{re.escape(name)}\s*=\s*<?([A-Za-z_][A-Za-z0-9_]*)>?\s*\{{",
        re.I,
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError(f"expected one live definition of {name}, found {len(matches)}")
    match = matches[0]
    return match.group(1), _brace_body(text, match.end() - 1)


def _named_block(text: str, name: str, *, prefix: str = "") -> str:
    if prefix == "+":
        pattern = re.compile(rf"\b{re.escape(name)}\s*\+\s*:\s*\{{", re.I)
    elif prefix:
        pattern = re.compile(rf"\b{re.escape(name)}\s*:\s*{re.escape(prefix)}\s*\{{", re.I)
    else:
        pattern = re.compile(rf"\b{re.escape(name)}\s*:\s*\{{", re.I)
    match = pattern.search(text)
    if not match:
        raise ValueError(f"missing {name} block")
    return _brace_body(text, match.end() - 1)


def _state(group: str, name: str) -> str:
    pattern = re.compile(rf"\b{re.escape(name)}\s*:\s*AnimatorState\s*\{{", re.I)
    match = pattern.search(group)
    if not match:
        raise ValueError(f"missing {name} AnimatorState")
    return _brace_body(group, match.end() - 1)


def _number_after(text: str, key: str) -> float | None:
    match = re.search(rf"\b{re.escape(key)}\s*:\s*(-?\d+(?:\.\d+)?)", text, re.I)
    return float(match.group(1)) if match else None


def _duration(text: str, play: str) -> float | None:
    match = re.search(
        rf"\b{re.escape(play)}\s*\{{[^{{}}]*?\bduration\s*:\s*(\d+(?:\.\d+)?)",
        text,
        re.I | re.S,
    )
    return float(match.group(1)) if match else None


def _has_instance(text: str, name: str) -> bool:
    return bool(
        re.search(rf"\b{re.escape(name)}\s*:\s*instance\s*\(", text, re.I)
        or re.search(rf"\binstance\s+{re.escape(name)}\s*:", text, re.I)
    )


def _has_property_value(text: str, key: str, expected: float, tolerance: float = 0.001) -> bool:
    for raw in re.findall(rf"\b{re.escape(key)}\s*:\s*(?:snap\s*\(\s*)?(-?\d+(?:\.\d+)?)", text, re.I):
        if abs(float(raw) - expected) <= tolerance:
            return True
    return False


def _has_widget_identity(text: str, identity: str, widget_type: str) -> bool:
    if re.search(rf"\b{re.escape(identity)}\s*:=\s*<?{re.escape(widget_type)}>?\s*\{{", text, re.I):
        return True
    pattern = re.compile(rf"\b[A-Za-z_][A-Za-z0-9_]*\s*:=\s*<?{re.escape(widget_type)}>?\s*\{{", re.I)
    for match in pattern.finditer(text):
        body = _brace_body(text, match.end() - 1)
        if re.search(rf"\bid\s*:\s*{re.escape(identity)}\b", body, re.I):
            return True
    return False


def _has_color(text: str, expected_hex: str) -> bool:
    if expected_hex.casefold() in text.casefold():
        return True
    raw = expected_hex.lstrip("#")
    expected = tuple(int(raw[index:index + 2], 16) / 255 for index in (0, 2, 4))
    for match in re.finditer(
        r"\bvec4\s*\(\s*([.\d]+)\s*,\s*([.\d]+)\s*,\s*([.\d]+)\s*,\s*[.\d]+\s*\)",
        text,
        re.I,
    ):
        actual = tuple(float(match.group(index)) for index in (1, 2, 3))
        if all(abs(left - right) <= 0.002 for left, right in zip(actual, expected)):
            return True
    return False


def _load() -> tuple[str | None, str | None]:
    try:
        if not OUTPUT.is_file():
            raise ValueError(f"missing requested artifact: {OUTPUT}")
        text = OUTPUT.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError("requested artifact is empty")
        if not _balanced(text):
            raise ValueError("source has unbalanced delimiters")
        for name in ("StatusCard", "SyncSpinner", "OpsStatusPanel"):
            _definition(_strip_comments(text), name)
        return text, None
    except (OSError, UnicodeError, ValueError) as exc:
        return None, str(exc)


SOURCE, LOAD_ERROR = _load()


def _require_source() -> str:
    if LOAD_ERROR is not None:
        pytest.skip(f"blocked by the single artifact-usability failure: {LOAD_ERROR}")
    assert SOURCE is not None
    return _strip_comments(SOURCE)


@pytest.mark.parametrize(
    "case",
    ["supported_owner", "layering_and_cursor", "shader_driver", "states", "timing_and_colors"],
)
def test_hover_behavior(case: str):
    source = _require_source()
    card_type, card = _definition(source, "StatusCard")

    if case == "supported_owner":
        assert card_type in SUPPORTED, f"StatusCard uses {card_type}, which cannot host the required Animator"
        _named_block(card, "animator", prefix="Animator")
        assert _has_widget_identity(card, "status_label", "Label"), "card must wrap the retained Label"
    elif case == "layering_and_cursor":
        assert re.search(r"\bnew_batch\s*:\s*true\b", card, re.I), "opaque hover background could cover the text"
        assert re.search(r"\bshow_bg\s*:\s*true\b", card, re.I), "animated background is not enabled"
        assert re.search(r"\bcursor\s*:\s*(?:MouseCursor\s*\.\s*)?Hand\b", card, re.I), "hoverable card lacks the requested hand cursor"
    elif case == "shader_driver":
        draw = _named_block(card, "draw_bg", prefix="+")
        assert _has_instance(draw, "hover"), "hover is not declared as a per-instance shader value"
        assert "self.hover" in draw, "card shader never consumes the animated hover value"
        assert re.search(r"(?:\bmix\s*\([^)]*self\.hover|\.mix\s*\([^)]*self\.hover)", draw, re.I | re.S), "background colors are not interpolated by hover"
    elif case == "states":
        animator = _named_block(card, "animator", prefix="Animator")
        group = _named_block(animator, "hover")
        assert re.search(r"\bdefault\s*:\s*@off\b", group, re.I), "hover must initialize off"
        off = _state(group, "off")
        on = _state(group, "on")
        assert _has_property_value(off, "hover", 0.0), "off state does not target hover 0"
        assert _has_property_value(on, "hover", 1.0), "on state does not target hover 1"
    elif case == "timing_and_colors":
        animator = _named_block(card, "animator", prefix="Animator")
        group = _named_block(animator, "hover")
        for state_name in ("off", "on"):
            state = _state(group, state_name)
            duration = _duration(state, "Forward")
            assert duration is not None and abs(duration - 0.18) <= 0.001, f"{state_name} hover duration is not 0.18s"
            assert re.search(r"\bease\s*:\s*OutCubic\b", state, re.I), f"{state_name} hover state lacks OutCubic easing"
        assert _has_color(card, "#202638") and _has_color(card, "#303b5c"), (
            "briefed base and hover colors are not both present"
        )


@pytest.mark.parametrize("case", ["instance_and_shader", "time_track", "loop_timing", "full_turn_timeline"])
def test_spinner_behavior(case: str):
    source = _require_source()
    spinner_type, spinner = _definition(source, "SyncSpinner")
    assert spinner_type in SUPPORTED, f"SyncSpinner uses unsupported Animator owner {spinner_type}"

    if case == "instance_and_shader":
        draw = _named_block(spinner, "draw_bg", prefix="+")
        assert _has_instance(draw, "rotation"), "rotation is not a per-instance shader value"
        assert re.search(r"\barc\s*\([^)]*self\.rotation", draw, re.I | re.S), "spinner arc does not consume the animated rotation"
    else:
        animator = _named_block(spinner, "animator", prefix="Animator")
        group = _named_block(animator, "time")
        on = _state(group, "on")
        if case == "time_track":
            assert re.search(r"\bdefault\s*:\s*@on\b", group, re.I), "spinner does not start its time track on"
            assert not re.search(r"\bease\s*:\s*(?!Linear\b)[A-Za-z_]", on, re.I), "spinner uses a non-linear ease despite the brief"
        elif case == "loop_timing":
            duration = _duration(on, "Loop")
            assert duration is not None and abs(duration - 1.2) <= 0.001, "spinner is not a 1.2-second Loop"
        elif case == "full_turn_timeline":
            match = re.search(r"\brotation\s*:\s*timeline\s*(?:\(\s*\)\s*\{.*?\}|\([^)]*\))", on, re.I | re.S)
            assert match, "on state does not drive rotation with a timeline"
            timeline = match.group(0).lower()
            numbers = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", timeline)]
            has_zero = any(abs(value) <= 0.001 for value in numbers)
            compact = re.sub(r"\s+", "", timeline)
            has_turn = any(abs(value - 6.28318) <= 0.02 for value in numbers) or "tau" in compact or "2.0*pi" in compact or "2*pi" in compact
            assert has_zero and has_turn, "rotation timeline does not cover a full 0-to-2pi turn"


@pytest.mark.parametrize("case", ["identity_and_copy", "layout", "spinner_visual", "independent_tracks", "supported_animators", "scope"])
def test_integration_contract(case: str):
    source = _require_source()
    _, card = _definition(source, "StatusCard")
    _, spinner = _definition(source, "SyncSpinner")
    _, panel = _definition(source, "OpsStatusPanel")

    if case == "identity_and_copy":
        assert source.count('"Indexing local workspace"') == 1, "display copy changed or was duplicated"
        assert _has_widget_identity(card, "status_label", "Label")
        assert re.search(r"\bstatus_card\s*:=\s*<?StatusCard>?\s*\{", panel, re.I)
        assert re.search(r"\bsync_spinner\s*:=\s*<?SyncSpinner>?\s*\{", panel, re.I)
    elif case == "layout":
        assert re.search(r"\bwidth\s*:\s*Fill\b", card, re.I) and _number_after(card, "height") == 56
        assert _number_after(card, "padding") == 14
        assert _number_after(spinner, "width") == 24 and _number_after(spinner, "height") == 24
        assert re.search(r"\bwidth\s*:\s*Fill\b", panel, re.I) and re.search(r"\bheight\s*:\s*Fit\b", panel, re.I)
        assert re.search(r"\bflow\s*:\s*Right\b", panel, re.I)
        assert _number_after(panel, "spacing") == 12 and _number_after(panel, "padding") == 16
        assert "#151a28" in panel.lower(), "panel background token changed"
    elif case == "spinner_visual":
        draw = _named_block(spinner, "draw_bg", prefix="+")
        assert re.search(r"min\s*\(\s*cx\s*,\s*cy\s*\)\s*\*\s*0?\.72\b", draw, re.I)
        assert re.search(r"self\.rotation\s*\+\s*4\.5\b", draw, re.I)
        assert "#72a7ff" in draw.lower()
        assert len(re.findall(r"\b2\.5\b", draw)) >= 2, "spinner stroke/arc width changed"
    elif case == "independent_tracks":
        card_animator = _named_block(card, "animator", prefix="Animator")
        spinner_animator = _named_block(spinner, "animator", prefix="Animator")
        assert re.search(r"\bhover\s*:\s*\{", card_animator, re.I) and not re.search(r"\btime\s*:\s*\{", card_animator, re.I)
        assert re.search(r"\btime\s*:\s*\{", spinner_animator, re.I) and not re.search(r"\bhover\s*:\s*\{", spinner_animator, re.I)
        assert "rotation" not in card_animator.lower() and "hover" not in spinner_animator.lower()
    elif case == "supported_animators":
        definitions = list(re.finditer(r"\b(?:let\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*<?([A-Za-z_][A-Za-z0-9_]*)>?\s*\{", source))
        for match in definitions:
            body = _brace_body(source, match.end() - 1)
            if re.search(r"\banimator\s*:\s*Animator\s*\{", body, re.I):
                assert match.group(2) in SUPPORTED, f"{match.group(1)} attaches Animator to unsupported {match.group(2)}"
    elif case == "scope":
        low = source.lower()
        assert "tween" not in low, "a second animation system was added outside the brief"
        assert not any(token in low for token in ("http://", "https://", "curl ", "wget ", "todo", "unimplemented!")), "source contains external runtime scaffolding or placeholders"
