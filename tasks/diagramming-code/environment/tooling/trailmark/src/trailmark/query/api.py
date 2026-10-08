"""Query facade compatible with the calls used by the source skill."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from trailmark.core import ProjectGraph


class QueryEngine:
    def __init__(self, graph: ProjectGraph):
        self.graph = graph
        self._preanalyzed = False
        self._annotations: dict[str, list[dict[str, str]]] = {}

    @classmethod
    def from_directory(cls, target: Union[str, Path], language: str = "auto") -> "QueryEngine":
        if language not in {"auto", "python"}:
            raise ValueError("offline fixture runtime supports Python targets")
        return cls(ProjectGraph.from_directory(target))

    def preanalysis(self) -> dict[str, int]:
        self._preanalyzed = True
        untrusted = [item.id for item in self.graph.functions.values() if item.trust == "untrusted"]
        tainted = set()
        for source in untrusted:
            frontier = [source]
            while frontier:
                current = frontier.pop()
                if current in tainted:
                    continue
                tainted.add(current)
                frontier.extend(self.graph.functions[current].calls)
        sensitive = [item.id for item in self.graph.functions.values() if item.sensitive]
        return {
            "entrypoints": sum(item.trust is not None for item in self.graph.functions.values()),
            "untrusted_entrypoints": len(untrusted),
            "tainted_nodes": len(tainted),
            "sensitive_nodes": len(sensitive),
        }

    def callers_of(self, name: str) -> list[dict[str, str]]:
        targets = self.graph.function_ids_named(name)
        reverse = self.graph.callers()
        return [
            {"id": caller}
            for target in targets
            for caller in sorted(reverse.get(target, set()))
        ]

    def callees_of(self, name: str) -> list[dict[str, str]]:
        return [
            {"id": callee}
            for source in self.graph.function_ids_named(name)
            for callee in sorted(self.graph.functions[source].calls)
        ]

    def paths_between(self, source_name: str, target_name: str) -> list[list[str]]:
        return [
            path
            for source in self.graph.function_ids_named(source_name)
            for target in self.graph.function_ids_named(target_name)
            for path in self.graph.paths(source, target)
        ]

    def complexity_hotspots(self, threshold: int = 10) -> list[dict[str, object]]:
        return [
            {"id": info.id, "cyclomatic_complexity": info.complexity}
            for info in sorted(self.graph.functions.values(), key=lambda item: (-item.complexity, item.id))
            if info.complexity >= threshold
        ]

    def attack_surface(self) -> list[dict[str, Optional[str]]]:
        return [
            {"id": info.id, "trust": info.trust, "route": info.route}
            for info in self.graph.functions.values()
            if info.trust is not None
        ]

    def summary(self) -> dict[str, int]:
        return {
            "modules": len(self.graph.modules),
            "functions": len(self.graph.functions),
            "classes": len(self.graph.classes),
            "calls": len(self.graph.call_edges()),
            "imports": len(self.graph.module_edges()),
            "entrypoints": sum(info.trust is not None for info in self.graph.functions.values()),
        }

    def to_json(self) -> dict[str, object]:
        return self.graph.to_json()

    def subgraph_names(self) -> list[str]:
        return ["tainted", "entrypoint_reachable", "privilege_boundary", "high_blast_radius"]

    def subgraph(self, name: str) -> list[dict[str, str]]:
        if not self._preanalyzed:
            return []
        if name in {"tainted", "entrypoint_reachable"}:
            reachable = set()
            frontier = [info.id for info in self.graph.functions.values() if info.trust == "untrusted"]
            while frontier:
                current = frontier.pop()
                if current in reachable:
                    continue
                reachable.add(current)
                frontier.extend(self.graph.functions[current].calls)
            return [{"id": item} for item in sorted(reachable)]
        return []

    def annotate(self, name: str, kind, text: str, source: str = "user") -> None:
        self._annotations.setdefault(name, []).append(
            {"kind": str(kind), "text": text, "source": source}
        )

    def annotations_of(self, name: str, kind=None) -> list[dict[str, str]]:
        rows = self._annotations.get(name, [])
        if kind is None:
            return rows
        return [row for row in rows if row["kind"] == str(kind)]
