from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS = Path(os.environ.get("SUBMISSION_ROOT", "/root/results"))
OUT = RESULTS / "orbit-ds"


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def all_files(*suffixes: str) -> list[Path]:
    if not OUT.is_dir():
        return []
    wanted = {item.lower() for item in suffixes}
    return [path for path in OUT.rglob("*") if path.is_file() and path.suffix.lower() in wanted]


def load_brief() -> dict:
    return json.loads((DATA / "brand_brief.json").read_text(encoding="utf-8"))


def load_inventory() -> list[dict]:
    return json.loads((DATA / "ui_inventory.json").read_text(encoding="utf-8"))


def flatten_w3c(node: object, path: tuple[str, ...] = ()) -> dict[tuple[str, ...], dict]:
    leaves: dict[tuple[str, ...], dict] = {}
    if isinstance(node, dict):
        if "$value" in node:
            leaves[path] = node
        else:
            for key, value in node.items():
                if not str(key).startswith("$"):
                    leaves.update(flatten_w3c(value, path + (str(key),)))
    return leaves


def token_leaves() -> dict[tuple[str, ...], dict]:
    merged: dict[tuple[str, ...], dict] = {}
    for path in all_files(".json"):
        try:
            payload = json.loads(read_text(path))
        except json.JSONDecodeError:
            continue
        candidate = flatten_w3c(payload)
        file_prefix = tuple(path.relative_to(OUT).with_suffix("").parts)
        for token_path, leaf in candidate.items():
            # Prefixing by file preserves identically named tokens spread across
            # foundations/theme files while still allowing suffix alias resolution.
            merged[file_prefix + token_path] = leaf
    return merged


def find_token(leaves: dict[tuple[str, ...], dict], required_parts: list[str]) -> tuple[str, ...] | None:
    wanted = [norm(item) for item in required_parts]
    candidates = []
    for path in leaves:
        parts = [norm(item) for item in path]
        if all(any(want == part or want in part for part in parts) for want in wanted):
            candidates.append(path)
    return min(candidates, key=lambda item: (len(item), ".".join(item))) if candidates else None


def resolve_token(path: tuple[str, ...], leaves: dict[tuple[str, ...], dict], seen: set[tuple[str, ...]] | None = None) -> object:
    seen = set() if seen is None else seen
    if path in seen:
        raise ValueError("cyclic token alias")
    seen.add(path)
    value = leaves[path].get("$value")
    if not isinstance(value, str):
        return value
    match = re.fullmatch(r"\{([^{}]+)\}", value.strip())
    if not match:
        return value
    target_parts = tuple(match.group(1).split("."))
    if target_parts in leaves:
        return resolve_token(target_parts, leaves, seen)
    target_norm = norm(match.group(1))
    matches = [candidate for candidate in leaves if norm(".".join(candidate)).endswith(target_norm)]
    if len(matches) == 1:
        return resolve_token(matches[0], leaves, seen)
    raise ValueError(f"unresolved token alias: {value}")


def hex_rgb(value: str) -> tuple[float, float, float]:
    raw = value.strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(char * 2 for char in raw)
    if len(raw) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", raw):
        raise ValueError(f"not a hex color: {value}")
    return tuple(int(raw[index:index + 2], 16) / 255 for index in (0, 2, 4))


def luminance(value: str) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    red, green, blue = hex_rgb(value)
    return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)


def contrast(a: str, b: str) -> float:
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def component_source(name: str) -> str:
    code_files = all_files(".tsx", ".ts", ".jsx", ".js")
    named = [path for path in code_files if norm(name) in norm(path.stem)]
    exported = [
        path for path in code_files
        if re.search(rf"\b(?:function|class|const)\s+{re.escape(name)}\b", read_text(path))
    ]
    selected = named or exported
    return "\n".join(read_text(path) for path in selected)


def test_token_foundations() -> None:
    brief = load_brief()
    leaves = token_leaves()
    assert len(leaves) >= 45, f"only {len(leaves)} token leaves were found; the foundation is materially incomplete"
    malformed = [".".join(path) for path, leaf in leaves.items() if "$type" not in leaf or "$value" not in leaf]
    assert not malformed, f"token leaves are not W3C-shaped: {malformed[:5]}"

    issues: list[str] = []
    for palette_id, expected in brief["approved_palette"].items():
        path = find_token(leaves, ["primitive", *palette_id.split(".")])
        if path is None:
            issues.append(f"missing primitive {palette_id}")
        else:
            try:
                actual = str(resolve_token(path, leaves)).upper()
            except ValueError as exc:
                issues.append(str(exc))
                continue
            if actual != expected.upper():
                issues.append(f"primitive {palette_id} is {actual}, expected {expected}")

    foundation_groups = {
        "font family": ("fontfamily", 2),
        "font size": ("fontsize", 5),
        "font weight": ("fontweight", 4),
        "line height": ("lineheight", 2),
        "spacing": ("spacing", 8),
        "radius": ("radius", 5),
        "shadow": ("shadow", 2),
    }
    normalized_paths = [norm(".".join(path)) for path in leaves]
    for label, (needle, minimum) in foundation_groups.items():
        count = sum(needle in path for path in normalized_paths)
        if count < minimum:
            issues.append(f"{label} has {count} tokens, expected at least {minimum}")
    assert not issues, "; ".join(issues[:12])


def test_theme_contract() -> None:
    brief = load_brief()
    leaves = token_leaves()
    issues: list[str] = []
    resolved: dict[str, dict[str, str]] = {"light": {}, "dark": {}}
    for theme, roles in brief["semantic_roles"].items():
        for role, palette_id in roles.items():
            path = find_token(leaves, [theme, *role.split(".")])
            if path is None:
                issues.append(f"missing semantic token {theme}.{role}")
                continue
            try:
                actual = str(resolve_token(path, leaves)).upper()
            except ValueError as exc:
                issues.append(f"{theme}.{role}: {exc}")
                continue
            expected = brief["approved_palette"][palette_id].upper()
            resolved[theme][role] = actual
            if actual != expected:
                issues.append(f"{theme}.{role} resolves to {actual}, expected approved {palette_id} ({expected})")

    css = "\n".join(read_text(path) for path in all_files(".css"))
    if len(re.findall(r"--[a-zA-Z0-9_-]+\s*:", css)) < 20:
        issues.append("CSS exposes fewer than 20 custom-property declarations")
    if not re.search(r"data-theme\s*=?.{0,8}dark|\[data-theme.{0,8}dark", css, re.I):
        issues.append("CSS has no explicit dark data-theme override")
    if not re.search(r"prefers-color-scheme\s*:\s*dark", css, re.I):
        issues.append("CSS does not follow the system dark preference when there is no override")
    if not re.search(r"var\(\s*--", css):
        issues.append("CSS does not consume its custom properties")

    for theme in ("light", "dark"):
        if len(resolved[theme]) != len(brief["semantic_roles"][theme]):
            continue
        canvas = resolved[theme]["background.canvas"]
        for role in ("text.primary", "text.secondary"):
            ratio = contrast(resolved[theme][role], canvas)
            if ratio + 1e-6 < 4.5:
                issues.append(f"{theme} {role}/canvas contrast is {ratio:.2f}:1, below 4.5:1")
        for role in ("border.default", "focus.ring", "brand.default"):
            ratio = contrast(resolved[theme][role], canvas)
            if ratio + 1e-6 < 3.0:
                issues.append(f"{theme} {role}/canvas contrast is {ratio:.2f}:1, below 3:1")
        on_brand_ratio = contrast(resolved[theme]["text.onBrand"], resolved[theme]["brand.default"])
        if on_brand_ratio + 1e-6 < 4.5:
            issues.append(f"{theme} text.onBrand/brand.default contrast is {on_brand_ratio:.2f}:1, below 4.5:1")
    assert not issues, "; ".join(issues[:14])


def test_component_scope() -> None:
    inventory = load_inventory()
    issues: list[str] = []
    for component in ("Button", "TextInput", "FormField", "Alert", "Modal"):
        source = component_source(component)
        if not source:
            issues.append(f"{component} source missing")
            continue
        rows = [row for row in inventory if row["canonical_component"] == component]
        if component in {"Button", "TextInput", "Alert"}:
            for intent in sorted({row["visual_intent"] for row in rows}):
                if not re.search(rf"['\"]{re.escape(intent)}['\"]", source, re.I):
                    issues.append(f"{component} does not expose observed {intent} intent")
        if component in {"Button", "TextInput", "Modal"}:
            for size in sorted({row["size"] for row in rows}):
                if not re.search(rf"['\"]{re.escape(size)}['\"]", source, re.I):
                    issues.append(f"{component} does not expose observed {size} size")
    assert not issues, "; ".join(issues)


def test_native_control_contracts() -> None:
    button = component_source("Button")
    text_input = component_source("TextInput")
    issues: list[str] = []
    button_checks = {
        "native button props": r"(?:ButtonHTMLAttributes\s*<\s*HTMLButtonElement|ComponentPropsWithoutRef\s*<\s*['\"]button['\"]\s*>)",
        "native button ref": r"forwardRef\s*<\s*HTMLButtonElement",
        "native button element": r"<button\b",
        "loading behavior": r"loading",
    }
    input_checks = {
        "native input props": r"(?:InputHTMLAttributes\s*<\s*HTMLInputElement|ComponentPropsWithoutRef\s*<\s*['\"]input['\"]\s*>)",
        "native input ref": r"forwardRef\s*<\s*HTMLInputElement",
        "native input element": r"<input\b",
    }
    for label, pattern in button_checks.items():
        if not re.search(pattern, button, re.I):
            issues.append(f"Button lacks {label}")
    for label, pattern in input_checks.items():
        if not re.search(pattern, text_input, re.I):
            issues.append(f"TextInput lacks {label}")
    assert not issues, "; ".join(issues)
