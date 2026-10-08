"""Generate Mermaid views from the deterministic AST graph."""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path
from typing import List, Optional

from trailmark.core import ProjectGraph, induced_edges, mermaid_id, mermaid_label


def _node(function_id: str, graph: ProjectGraph, suffix: str = "") -> str:
    info = graph.functions[function_id]
    label = f"{info.name}, {info.kind}{suffix}"
    return f'    {mermaid_id(function_id)}["{mermaid_label(label)}"]'


def render_module_dependencies(graph: ProjectGraph, direction: str = "LR") -> str:
    edges = sorted(graph.module_edges())
    nodes = sorted({value for edge in edges for value in edge})
    lines = [f"flowchart {direction}"]
    for module in nodes:
        lines.append(f'    {mermaid_id(module)}["{mermaid_label(module)}, module"]')
    for source, target in edges:
        lines.append(f"    {mermaid_id(source)} --> {mermaid_id(target)}")
    if not nodes:
        lines.append('    no_modules["No local module dependencies found"]')
    return "\n".join(lines)


def render_data_flow(graph: ProjectGraph, focus: str, direction: str = "TB") -> str:
    targets = graph.function_ids_named(focus)
    if not targets:
        return f'flowchart {direction}\n    missing["Focus function not found: {mermaid_label(focus)}"]'
    target = targets[0]
    entrypoints = sorted(
        info.id for info in graph.functions.values() if info.trust is not None
    )
    paths = [
        path
        for source in entrypoints
        for path in graph.paths(source, target)
    ]
    edges = induced_edges(paths)
    nodes = sorted({item for path in paths for item in path})
    lines = [f"flowchart {direction}"]
    for function_id in nodes:
        info = graph.functions[function_id]
        shape = _node(function_id, graph)
        if info.trust == "untrusted":
            shape = shape.replace('["', '(["').replace('"]', '"])') + ":::untrusted"
        elif info.trust == "authenticated":
            shape += ":::authenticated"
        elif info.sensitive:
            shape += ":::sensitive"
        lines.append(shape)
    for source, destination in sorted(edges):
        lines.append(f"    {mermaid_id(source)} --> {mermaid_id(destination)}")
    if not nodes:
        lines.append('    no_path["No entrypoint reaches the focus function"]')
    lines.extend(
        [
            "    classDef untrusted fill:#dbeafe,stroke:#2563eb,color:#1e3a8a",
            "    classDef authenticated fill:#dcfce7,stroke:#16a34a,color:#14532d",
            "    classDef sensitive fill:#fee2e2,stroke:#dc2626,color:#7f1d1d",
        ]
    )
    return "\n".join(lines)


def render_call_graph(graph: ProjectGraph, focus: str, depth: int = 2, direction: str = "TB") -> str:
    matches = graph.function_ids_named(focus)
    if not matches:
        return f'flowchart {direction}\n    missing["Focus function not found"]'
    start = matches[0]
    reverse = graph.callers()
    seen = {start}
    queue = deque([(start, 0)])
    edges: set[tuple[str, str]] = set()
    while queue:
        current, distance = queue.popleft()
        if distance >= depth:
            continue
        neighbors = {(current, item) for item in graph.functions[current].calls}
        neighbors |= {(item, current) for item in reverse.get(current, set())}
        for edge in sorted(neighbors):
            edges.add(edge)
            neighbor = edge[1] if edge[0] == current else edge[0]
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, distance + 1))
    lines = [f"flowchart {direction}"]
    lines.extend(_node(item, graph) for item in sorted(seen))
    lines.extend(f"    {mermaid_id(a)} --> {mermaid_id(b)}" for a, b in sorted(edges))
    return "\n".join(lines)


def render_class_hierarchy(graph: ProjectGraph) -> str:
    lines = ["classDiagram"]
    for info in sorted(graph.classes.values(), key=lambda item: item.id):
        lines.append(f"    class {mermaid_id(info.id)}")
        for base in info.bases:
            lines.append(f"    {mermaid_id(base)} <|-- {mermaid_id(info.id)}")
    if len(lines) == 1:
        lines.append('    class No_inheritance_found')
    return "\n".join(lines)


def render_containment(graph: ProjectGraph) -> str:
    lines = ["classDiagram"]
    for info in sorted(graph.classes.values(), key=lambda item: item.id):
        lines.append(f"    class {mermaid_id(info.id)} {{")
        lines.extend(f"        +{method}()" for method in info.methods)
        lines.append("    }")
    if len(lines) == 1:
        lines.append("    class No_classes_found")
    return "\n".join(lines)


def render_complexity(graph: ProjectGraph, threshold: int = 10, direction: str = "TB") -> str:
    selected = {
        item.id: item
        for item in graph.functions.values()
        if item.complexity >= threshold
    }
    lines = [f"flowchart {direction}"]
    for function_id, info in sorted(selected.items()):
        style = "low" if info.complexity < 5 else "medium" if info.complexity <= 10 else "high"
        lines.append(_node(function_id, graph, suffix=f", CC={info.complexity}") + f":::{style}")
    for source, target in sorted(graph.call_edges()):
        if source in selected and target in selected:
            lines.append(f"    {mermaid_id(source)} --> {mermaid_id(target)}")
    if not selected:
        lines.append('    no_hotspots["No functions meet the complexity threshold"]')
    lines.extend(
        [
            "    classDef low fill:#dcfce7,stroke:#16a34a,color:#14532d",
            "    classDef medium fill:#fef3c7,stroke:#d97706,color:#78350f",
            "    classDef high fill:#fee2e2,stroke:#dc2626,color:#7f1d1d",
        ]
    )
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", "-t", required=True)
    parser.add_argument("--language", "-l", default="python")
    parser.add_argument(
        "--type",
        "-T",
        required=True,
        choices=("call-graph", "class-hierarchy", "module-deps", "containment", "complexity", "data-flow"),
    )
    parser.add_argument("--focus", "-f")
    parser.add_argument("--depth", "-d", type=int, default=2)
    parser.add_argument("--direction", choices=("TB", "LR"), default="TB")
    parser.add_argument("--threshold", type=int, default=10)
    args = parser.parse_args(argv)
    if args.language not in {"auto", "python"}:
        parser.error("offline fixture runtime supports Python targets")
    graph = ProjectGraph.from_directory(Path(args.target))
    if args.type == "module-deps":
        output = render_module_dependencies(graph, args.direction)
    elif args.type == "data-flow":
        output = render_data_flow(graph, args.focus or "run_template", args.direction)
    elif args.type == "call-graph":
        if not args.focus:
            parser.error("call-graph requires --focus for this fixture")
        output = render_call_graph(graph, args.focus, args.depth, args.direction)
    elif args.type == "class-hierarchy":
        output = render_class_hierarchy(graph)
    elif args.type == "containment":
        output = render_containment(graph)
    else:
        output = render_complexity(graph, args.threshold, args.direction)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
