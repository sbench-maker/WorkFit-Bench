from __future__ import annotations

import ast
from dataclasses import dataclass, field
import html
from pathlib import Path
import re
from typing import Optional


OUTPUT = Path("/root/results/security_architecture.md")
SOURCE = Path("/root/data/relay_service")

MERMAID_RE = re.compile(r"```\s*mermaid[^\n]*\n(.*?)```", re.IGNORECASE | re.DOTALL)
EDGE_RE = re.compile(
    r"^\s*([A-Za-z_][\w.:-]*).*?(?:-->|-\.->|\.\.->|==>)\s*(?:\|[^|]*\|\s*)?([A-Za-z_][\w.:-]*)"
)
ROUND_NODE_RE = re.compile(
    r"^\s*([A-Za-z_][\w.:-]*)\s*\(\[\s*[\"']?(.*?)[\"']?\s*\]\)"
)
NODE_RE = re.compile(
    r"^\s*([A-Za-z_][\w.:-]*)\s*(?:\[|\(|\{)\s*[\"']?(.*?)[\"']?\s*(?:\]|\)|\})"
)


@dataclass
class MermaidGraph:
    raw: str
    nodes: dict[str, str] = field(default_factory=dict)
    edges: set[tuple[str, str]] = field(default_factory=set)
    styles: dict[str, set[str]] = field(default_factory=dict)
    rounded: set[str] = field(default_factory=set)


def _artifact_text() -> str:
    if not OUTPUT.is_file():
        return ""
    try:
        return OUTPUT.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _clean_label(value: str) -> str:
    value = html.unescape(value).replace("#quot;", '"').strip()
    value = re.sub(r":::[A-Za-z_][\w-]*\s*$", "", value).strip()
    value = re.sub(r"[\]\)}]+\s*$", "", value).strip()
    return value.strip(" \"'")


def _parse_mermaid(raw: str) -> MermaidGraph:
    graph = MermaidGraph(raw=raw)
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("%%") or stripped.lower().startswith("classdef"):
            continue

        rounded = ROUND_NODE_RE.match(line)
        node_match = rounded or NODE_RE.match(line)
        if node_match and not stripped.lower().startswith(("flowchart", "graph", "class ", "style ")):
            node_id, label = node_match.groups()
            graph.nodes[node_id] = _clean_label(label)
            if rounded:
                graph.rounded.add(node_id)
            inline_style = re.search(r":::\s*([A-Za-z_][\w-]*)", line)
            if inline_style:
                graph.styles.setdefault(node_id, set()).add(inline_style.group(1).lower())

        edge = EDGE_RE.match(line)
        if edge:
            source, target = edge.groups()
            graph.edges.add((source, target))
            graph.nodes.setdefault(source, source)
            graph.nodes.setdefault(target, target)

        class_match = re.match(
            r"^\s*class\s+([A-Za-z_][\w.:-]*(?:\s*,\s*[A-Za-z_][\w.:-]*)*)\s+([A-Za-z_][\w-]*)\s*$",
            line,
            re.IGNORECASE,
        )
        if class_match:
            node_ids, class_name = class_match.groups()
            for node_id in re.split(r"\s*,\s*", node_ids):
                graph.styles.setdefault(node_id, set()).add(class_name.lower())
    return graph


def _graphs() -> list[MermaidGraph]:
    return [_parse_mermaid(block) for block in MERMAID_RE.findall(_artifact_text())]


def _normalized(value: str) -> str:
    value = html.unescape(value).replace("#quot;", '"').lower()
    value = value.replace("\\", "/").replace(".py", "")
    value = re.sub(r"\b(module|function|method|handler|route|endpoint)\b", " ", value)
    value = value.replace("/", ".").replace(":", ".")
    value = re.sub(r"[^a-z0-9_.]+", " ", value)
    return " ".join(value.split())


def _matches(value: str, symbol: str) -> bool:
    candidate = _normalized(value)
    expected = _normalized(symbol)
    short = expected.removeprefix("relay.")
    forms = {expected, short, expected.rsplit(".", 1)[-1]}
    for form in forms:
        if not form:
            continue
        if candidate == form or candidate.startswith(form + " ") or candidate.endswith(" " + form):
            return True
        if re.search(rf"(?<![a-z0-9_]){re.escape(form)}(?![a-z0-9_])", candidate):
            return True
    return False


def _ids_for(graph: MermaidGraph, symbol: str) -> set[str]:
    return {
        node_id
        for node_id, label in graph.nodes.items()
        if _matches(label, symbol) or _matches(node_id, symbol)
    }


def _has_edge(graph: MermaidGraph, source: str, target: str) -> bool:
    sources = _ids_for(graph, source)
    targets = _ids_for(graph, target)
    return any((left, right) in graph.edges for left in sources for right in targets)


def _reachable(graph: MermaidGraph, source: str, target: str) -> bool:
    starts = _ids_for(graph, source)
    goals = _ids_for(graph, target)
    frontier = list(starts)
    seen = set(starts)
    adjacency: dict[str, set[str]] = {}
    for left, right in graph.edges:
        adjacency.setdefault(left, set()).add(right)
    while frontier:
        current = frontier.pop()
        if current in goals:
            return True
        for child in adjacency.get(current, set()):
            if child not in seen:
                seen.add(child)
                frontier.append(child)
    return False


MODULES = [
    "relay.app",
    "relay.api.webhooks",
    "relay.api.preview",
    "relay.api.admin",
    "relay.security.signatures",
    "relay.security.auth",
    "relay.validation.events",
    "relay.repositories.events",
    "relay.services.pipeline",
    "relay.templates.catalog",
    "relay.rendering.engine",
    "relay.rendering.runtime",
    "relay.sending.queue",
    "relay.core.storage",
]

MODULE_EDGES = [
    ("relay.app", "relay.api.webhooks"),
    ("relay.app", "relay.api.preview"),
    ("relay.app", "relay.api.admin"),
    ("relay.api.webhooks", "relay.security.signatures"),
    ("relay.api.webhooks", "relay.validation.events"),
    ("relay.api.webhooks", "relay.services.pipeline"),
    ("relay.api.preview", "relay.validation.preview"),
    ("relay.api.preview", "relay.rendering.engine"),
    ("relay.api.admin", "relay.security.auth"),
    ("relay.api.admin", "relay.repositories.events"),
    ("relay.api.admin", "relay.services.pipeline"),
    ("relay.security.auth", "relay.repositories.operators"),
    ("relay.repositories.events", "relay.core.storage"),
    ("relay.services.pipeline", "relay.templates.catalog"),
    ("relay.services.pipeline", "relay.rendering.engine"),
    ("relay.services.pipeline", "relay.sending.queue"),
    ("relay.rendering.engine", "relay.rendering.runtime"),
]

FLOW_FUNCTIONS = [
    "receive_event",
    "preview_template",
    "replay_event",
    "process_event",
    "render_template",
    "run_template",
]


def _module_graph() -> Optional[MermaidGraph]:
    graphs = _graphs()
    if not graphs:
        return None
    return max(graphs, key=lambda graph: sum(bool(_ids_for(graph, module)) for module in MODULES))


def _flow_graph() -> Optional[MermaidGraph]:
    graphs = _graphs()
    if not graphs:
        return None
    return max(graphs, key=lambda graph: sum(bool(_ids_for(graph, function)) for function in FLOW_FUNCTIONS))


def _module_name(root: Path, path: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _source_call_edges() -> set[tuple[str, str]]:
    trees: dict[str, ast.Module] = {}
    names: dict[str, set[str]] = {}
    imports: dict[str, dict[str, str]] = {}
    for path in sorted(SOURCE.rglob("*.py")):
        module = _module_name(SOURCE, path)
        if not module:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        trees[module] = tree
        names[module] = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        imports[module] = {
            alias.asname or alias.name: f"{node.module}:{alias.name}"
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module
            for alias in node.names
        }

    edges: set[tuple[str, str]] = set()
    all_functions = {(module, name) for module, values in names.items() for name in values}
    for module, tree in trees.items():
        for function in tree.body:
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for call in ast.walk(function):
                if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
                    continue
                target_name = call.func.id
                imported = imports[module].get(target_name)
                if imported:
                    imported_module, imported_name = imported.split(":", 1)
                    if (imported_module, imported_name) in all_functions:
                        edges.add((function.name, imported_name))
                elif target_name in names[module]:
                    edges.add((function.name, target_name))
    return edges


def _known_function_names() -> set[str]:
    return {
        node.name
        for path in SOURCE.rglob("*.py")
        for node in ast.parse(path.read_text(encoding="utf-8")).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _function_name(graph: MermaidGraph, node_id: str, known: set[str]) -> Optional[str]:
    label = graph.nodes.get(node_id, node_id)
    matches = [name for name in known if _matches(label, name) or _matches(node_id, name)]
    return matches[0] if len(matches) == 1 else None


def _is_untrusted(graph: MermaidGraph, node_id: str) -> bool:
    label = _normalized(graph.nodes.get(node_id, node_id))
    styles = graph.styles.get(node_id, set())
    if any(word in label for word in ("authenticated", "trusted", "admin", "privileged")) and not (
        {"untrusted", "public", "external"} & styles
    ):
        return False
    return bool(
        {"untrusted", "public", "external", "entrypoint"} & styles
        or node_id in graph.rounded
        or any(word in label for word in ("untrusted", "public", "external input"))
    )


def test_module_map_scope_and_direction() -> None:
    graph = _module_graph()
    assert graph is not None, "no Mermaid block can be identified as the module dependency map"
    assert re.search(r"(?im)^\s*(?:flowchart|graph)\s+LR\b", graph.raw), (
        "the module dependency map is not left-to-right as requested"
    )
    missing = [module for module in MODULES if not _ids_for(graph, module)]
    assert not missing, "the dependency map omits material modules: " + ", ".join(missing)


def test_module_dependencies_match_code() -> None:
    graph = _module_graph()
    assert graph is not None, "no module dependency map was found"
    missing = [f"{source} -> {target}" for source, target in MODULE_EDGES if not _has_edge(graph, source, target)]
    assert not missing, "the dependency map omits direct imports that define service boundaries: " + "; ".join(missing)


def test_attack_surface_path_coverage() -> None:
    graph = _flow_graph()
    assert graph is not None, "no Mermaid block can be identified as the run_template data-flow view"
    missing_paths = [
        handler
        for handler in ("receive_event", "preview_template", "replay_event")
        if not _reachable(graph, handler, "run_template")
    ]
    assert not missing_paths, "request handlers with a real run_template path are missing: " + ", ".join(missing_paths)
    material_edges = [
        ("receive_event", "process_event"),
        ("replay_event", "process_event"),
        ("preview_template", "render_template"),
        ("process_event", "render_template"),
        ("render_template", "run_template"),
    ]
    missing_edges = [f"{a} -> {b}" for a, b in material_edges if not _has_edge(graph, a, b)]
    assert not missing_edges, "the view collapses or omits material code steps: " + "; ".join(missing_edges)


def test_data_flow_edges_are_code_grounded() -> None:
    graph = _flow_graph()
    assert graph is not None, "no run_template data-flow view was found"
    known = _known_function_names()
    allowed = _source_call_edges()
    fabricated = []
    for left, right in graph.edges:
        source = _function_name(graph, left, known)
        target = _function_name(graph, right, known)
        if source and target and (source, target) not in allowed:
            fabricated.append(f"{source} -> {target}")
    assert not fabricated, "the data-flow view invents direct function calls: " + "; ".join(sorted(fabricated))


def test_untrusted_entrypoints_are_distinguished() -> None:
    graph = _flow_graph()
    assert graph is not None, "no run_template data-flow view was found"
    markers: dict[str, bool] = {}
    for function in ("receive_event", "preview_template", "replay_event"):
        ids = _ids_for(graph, function)
        assert ids, f"{function} is absent from the attack-surface view"
        markers[function] = any(_is_untrusted(graph, node_id) for node_id in ids)
    assert markers["receive_event"] and markers["preview_template"], (
        "both public handlers must be visibly marked as untrusted entry points"
    )
    assert not markers["replay_event"], (
        "the authenticated replay handler is marked the same way as untrusted public entry points"
    )
