from __future__ import annotations

import os
import re
from pathlib import Path


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data")).resolve()
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results")).resolve()
OUTPUT_PATH = RESULTS_DIR / "AGENTS.md"


def _readable_output() -> str | None:
    try:
        raw = OUTPUT_PATH.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return text if text.strip() else None


def _normalized(text: str) -> str:
    value = text.lower().replace("\\", "/")
    value = value.replace("get-design-context", "get_design_context")
    value = value.replace("get design context", "get_design_context")
    value = value.replace("get-screenshot", "get_screenshot")
    value = value.replace("get screenshot", "get_screenshot")
    value = value.replace("get-metadata", "get_metadata")
    value = value.replace("get metadata", "get_metadata")
    value = value.replace("http only", "http-only").replace("httponly", "http-only")
    value = re.sub(r"[`*#>|\[\](){}\"']", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _contains_any(text: str, alternatives: tuple[str, ...]) -> bool:
    return any(_normalized(item) in text for item in alternatives)


def _semantic_text_or_none() -> str | None:
    raw = _readable_output()
    return None if raw is None else _normalized(raw)


def test_artifact_is_usable_and_preserves_existing_instructions() -> None:
    raw = _readable_output()
    assert raw is not None, "`/root/results/AGENTS.md` is missing, empty, unreadable, or not UTF-8"
    text = _normalized(raw)
    assert 900 <= len(raw) <= 32768, (
        "AGENTS.md is too sparse to guide the requested scope or too large for routine Codex loading"
    )
    assert "figma" in text and ("rule" in text or "guidance" in text), (
        "the file does not contain recognizable Figma-to-code rules"
    )
    assert "src/services/apiclient.ts" in text and _contains_any(
        text,
        ("route every http request through", "all network requests go through", "use src/services/apiclient.ts for"),
    ), "the existing centralized HTTP-client safeguard was not preserved"
    assert "session token" in text and "http-only cookie" in text and _contains_any(
        text,
        ("never read or persist", "do not read or persist", "must not read or persist"),
    ), "the existing session-token safeguard was not preserved"
    assert "src/app/routes.generated.ts" in text and _contains_any(
        text,
        ("do not edit", "never edit", "must not edit"),
    ) and "npm run routes:generate" in text, "the generated-route-file safeguard was not preserved"
    placeholders = re.findall(
        r"\[(?:your|component_directory|token_location|add any)[^\]]*\]|\b(?:todo|tbd):?\b",
        raw,
        flags=re.IGNORECASE,
    )
    assert not placeholders, f"unresolved template placeholders make the rule file unsafe to adopt: {placeholders[:3]}"


def test_component_locations_and_reuse_rules() -> None:
    text = _semantic_text_or_none()
    if text is None:
        return
    assert "src/design-system/primitives" in text, (
        "the reusable primitive destination from the project snapshot is absent"
    )
    assert "src/features" in text and "component" in text, (
        "the feature-level destination for domain composition is absent"
    )
    assert _contains_any(text, ("reuse", "search", "check")) and _contains_any(
        text,
        ("before creating", "before adding", "instead of duplicating", "avoid duplicating", "do not duplicate"),
    ), "the rules do not direct future work to discover and reuse existing primitives first"
    assert _contains_any(text, ("reusable", "shared", "broadly reusable")) and _contains_any(
        text,
        ("domain", "feature-specific", "feature composition", "feature behavior"),
    ), "the primitive-versus-feature ownership boundary is not made actionable"


def test_component_api_and_import_conventions() -> None:
    text = _semantic_text_or_none()
    if text is None:
        return
    assert "pascalcase" in text and _contains_any(text, ("named export", "named exports")), (
        "the observed component naming and export conventions are incomplete"
    )
    assert "@/" in text and _contains_any(
        text,
        ("path alias", "absolute import", "import shared ui through", "use @/"),
    ), "the repository's @/ import convention is missing"
    assert "classname" in text and _contains_any(text, ("merge", "composition", "accept")), (
        "the composable className convention is missing"
    )
    assert _contains_any(text, ("native element props", "native props", "buttonhtmlattributes", "htmlattributes")), (
        "the established native-prop extension pattern is not captured"
    )
    assert _contains_any(text, ("union", "variant")), "the typed component-variant pattern is absent"


def test_application_architecture_boundaries() -> None:
    text = _semantic_text_or_none()
    if text is None:
        return
    assert "tanstack query" in text and _contains_any(text, ("server-state", "server state")), (
        "the project's server-state owner is missing or mischaracterized"
    )
    assert "src/app/router.tsx" in text and _contains_any(
        text,
        ("register route", "routing", "new routes"),
    ), "the editable routing integration point is missing"
    assert _contains_any(text, ("nearest component", "local interaction state", "local ui state", "component state")), (
        "the boundary between server state and local interaction state is not captured"
    )


def test_css_module_and_token_rules() -> None:
    text = _semantic_text_or_none()
    if text is None:
        return
    assert _contains_any(text, ("css module", "css modules", ".module.css")), (
        "the observed styling mechanism is absent"
    )
    assert "src/styles/tokens.css" in text, "the actual design-token source is absent"
    for family in ("--color-", "--space-", "--radius-"):
        assert family in text, f"the {family} token family is not covered"
    assert _contains_any(
        text,
        ("never hardcode", "do not hardcode", "avoid hardcoded", "must not hardcode"),
    ) and _contains_any(text, ("hex", "rgb", "raw spacing", "literal color", "literal spacing")), (
        "the rules do not prevent bypassing available tokens with literal colors or spacing"
    )
    assert _contains_any(text, ("dynamic", "css custom property", "custom property")) and "token" in text, (
        "the existing token-backed dynamic-style exception is not represented"
    )


def test_figma_asset_rules() -> None:
    text = _semantic_text_or_none()
    if text is None:
        return
    assert "localhost" in text and _contains_any(text, ("use", "retrieve", "download")), (
        "handling for Figma MCP localhost asset sources is absent"
    )
    assert "public/figma-assets" in text, "the repository's persisted Figma asset directory is absent"
    assert _contains_any(text, ("do not substitute a placeholder", "no placeholder", "never use a placeholder")), (
        "the rules allow supplied Figma assets to be replaced by placeholders"
    )
    assert "do not" in text and _contains_any(text, ("icon package", "icon library", "new icon")), (
        "the rules do not prevent unnecessary icon-package additions when assets are supplied"
    )


def test_figma_context_screenshot_and_implementation_order() -> None:
    text = _semantic_text_or_none()
    if text is None:
        return
    context_at = text.find("get_design_context")
    screenshot_at = text.find("get_screenshot")
    implementation_markers = [
        value
        for value in (text.find("begin implementation"), text.find("start implementation"), text.find("implementation only after"))
        if value >= 0
    ]
    assert context_at >= 0 and screenshot_at >= 0 and implementation_markers, (
        "the rules do not make context, screenshot, and implementation gating explicit"
    )
    assert context_at < screenshot_at < min(implementation_markers), (
        "the required dependency order is not context, then screenshot, then implementation"
    )
    both_window = text[screenshot_at : min(implementation_markers) + 180]
    assert _contains_any(both_window, ("both", "until", "only after")), (
        "implementation is not clearly gated on having both structured context and screenshot"
    )


def test_figma_fallback_translation_and_validation() -> None:
    text = _semantic_text_or_none()
    if text is None:
        return
    assert "get_metadata" in text and _contains_any(text, ("truncated", "too large", "oversized")), (
        "the captured metadata fallback for oversized context is missing"
    )
    assert text.count("get_design_context") >= 2 and _contains_any(
        text,
        ("rerun", "re-run", "refetch", "fetch again", "call again"),
    ), "the fallback does not return to design context for the smaller node set"
    assert "tailwind" in text and "react" in text and _contains_any(
        text,
        ("not final", "do not paste", "translate", "adapt"),
    ) and _contains_any(text, ("css module", "css modules", ".module.css")), (
        "the rules do not explain how to adapt generic Figma output to this project's stack"
    )
    assert "figma" in text and "screenshot" in text and _contains_any(
        text,
        ("1:1", "parity", "compare", "validate"),
    ) and _contains_any(text, ("behavior", "interaction", "interactive")), (
        "final validation does not cover both visual and behavioral parity"
    )
