"""Deterministic Python AST graph extraction for the offline task runtime."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Iterable, Optional, Tuple, Union


@dataclass
class FunctionInfo:
    id: str
    module: str
    name: str
    kind: str = "function"
    class_name: Optional[str] = None
    trust: Optional[str] = None
    route: Optional[str] = None
    sensitive: bool = False
    complexity: int = 1
    calls: set[str] = field(default_factory=set)


@dataclass
class ClassInfo:
    id: str
    module: str
    name: str
    bases: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)


@dataclass
class ModuleInfo:
    name: str
    path: Path
    dependencies: set[str] = field(default_factory=set)
    imported_symbols: dict[str, str] = field(default_factory=dict)
    imported_modules: dict[str, str] = field(default_factory=dict)


def _module_name(root: Path, path: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _decorator_name(node: ast.expr) -> Tuple[str, Optional[str]]:
    route = None
    target = node
    if isinstance(node, ast.Call):
        target = node.func
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            route = node.args[0].value
    if isinstance(target, ast.Name):
        return target.id, route
    if isinstance(target, ast.Attribute):
        return target.attr, route
    return "", route


def _complexity(node: ast.AST) -> int:
    branches = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.IfExp)
    score = 1 + sum(isinstance(child, branches) for child in ast.walk(node))
    score += sum(
        max(0, len(child.values) - 1)
        for child in ast.walk(node)
        if isinstance(child, ast.BoolOp)
    )
    return score


def _resolve_relative(current: str, imported: Optional[str], level: int) -> str:
    if level == 0:
        return imported or ""
    package = current.split(".")[:-1]
    keep = max(0, len(package) - (level - 1))
    parts = package[:keep]
    if imported:
        parts.extend(imported.split("."))
    return ".".join(parts)


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", value)
    if not cleaned or cleaned[0].isdigit():
        cleaned = "n_" + cleaned
    return cleaned


def _escape(value: str) -> str:
    return value.replace('"', "#quot;")


class ProjectGraph:
    def __init__(self, root: Path):
        self.root = root
        self.modules: dict[str, ModuleInfo] = {}
        self.functions: dict[str, FunctionInfo] = {}
        self.classes: dict[str, ClassInfo] = {}
        self._trees: dict[str, ast.Module] = {}

    @classmethod
    def from_directory(cls, target: Union[str, Path]) -> "ProjectGraph":
        graph = cls(Path(target).resolve())
        graph._build()
        return graph

    def _build(self) -> None:
        paths = sorted(self.root.rglob("*.py"))
        for path in paths:
            module = _module_name(self.root, path)
            if not module:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            info = ModuleInfo(name=module, path=path)
            self.modules[module] = info
            self._trees[module] = tree

        local_modules = set(self.modules)
        for module, tree in self._trees.items():
            info = self.modules[module]
            for node in tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported = alias.name
                        if imported in local_modules:
                            info.dependencies.add(imported)
                        info.imported_modules[alias.asname or imported.split(".")[0]] = imported
                elif isinstance(node, ast.ImportFrom):
                    imported = _resolve_relative(module, node.module, node.level)
                    if imported in local_modules and imported != module:
                        info.dependencies.add(imported)
                    for alias in node.names:
                        info.imported_symbols[alias.asname or alias.name] = f"{imported}:{alias.name}"
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._add_function(module, node)
                elif isinstance(node, ast.ClassDef):
                    self._add_class(module, node)

        for module, tree in self._trees.items():
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._resolve_calls(module, node, self.functions[f"{module}:{node.name}"])
                elif isinstance(node, ast.ClassDef):
                    for child in node.body:
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            key = f"{module}:{node.name}.{child.name}"
                            self._resolve_calls(module, child, self.functions[key], class_name=node.name)

    def _add_function(
        self,
        module: str,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        class_name: Optional[str] = None,
    ) -> None:
        qualified = f"{class_name}.{node.name}" if class_name else node.name
        trust = None
        route = None
        sensitive = False
        for decorator in node.decorator_list:
            name, decorator_route = _decorator_name(decorator)
            if name == "public_route":
                trust = "untrusted"
                route = decorator_route
            elif name == "admin_route":
                trust = "authenticated"
                route = decorator_route
            elif name == "sensitive_sink":
                sensitive = True
        function_id = f"{module}:{qualified}"
        self.functions[function_id] = FunctionInfo(
            id=function_id,
            module=module,
            name=node.name,
            kind="method" if class_name else "function",
            class_name=class_name,
            trust=trust,
            route=route,
            sensitive=sensitive,
            complexity=_complexity(node),
        )

    def _add_class(self, module: str, node: ast.ClassDef) -> None:
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(base.attr)
        class_info = ClassInfo(id=f"{module}:{node.name}", module=module, name=node.name, bases=bases)
        self.classes[class_info.id] = class_info
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._add_function(module, child, class_name=node.name)
                class_info.methods.append(child.name)

    def _resolve_calls(
        self,
        module: str,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        owner: FunctionInfo,
        class_name: Optional[str] = None,
    ) -> None:
        imports = self.modules[module]
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            target = None
            if isinstance(child.func, ast.Name):
                name = child.func.id
                imported = imports.imported_symbols.get(name)
                if imported in self.functions:
                    target = imported
                elif f"{module}:{name}" in self.functions:
                    target = f"{module}:{name}"
                elif class_name and f"{module}:{class_name}.{name}" in self.functions:
                    target = f"{module}:{class_name}.{name}"
            elif isinstance(child.func, ast.Attribute):
                attr = child.func.attr
                if isinstance(child.func.value, ast.Name):
                    base = child.func.value.id
                    imported_module = imports.imported_modules.get(base)
                    candidate = f"{imported_module}:{attr}" if imported_module else ""
                    if candidate in self.functions:
                        target = candidate
                    elif base == "self" and class_name:
                        candidate = f"{module}:{class_name}.{attr}"
                        if candidate in self.functions:
                            target = candidate
            if target and target != owner.id:
                owner.calls.add(target)

    def callers(self) -> dict[str, set[str]]:
        reverse = {function_id: set() for function_id in self.functions}
        for source, function in self.functions.items():
            for target in function.calls:
                reverse.setdefault(target, set()).add(source)
        return reverse

    def function_ids_named(self, name: str) -> list[str]:
        return [key for key, value in self.functions.items() if value.name == name or key.endswith(name)]

    def paths(self, source: str, target: str, max_depth: int = 20) -> list[list[str]]:
        found: list[list[str]] = []

        def visit(current: str, path: list[str]) -> None:
            if len(path) > max_depth or current in path[:-1]:
                return
            if current == target:
                found.append(path)
                return
            for child in sorted(self.functions[current].calls):
                visit(child, path + [child])

        visit(source, [source])
        return found

    def module_edges(self) -> set[tuple[str, str]]:
        return {
            (module, dependency)
            for module, info in self.modules.items()
            for dependency in info.dependencies
        }

    def call_edges(self) -> set[tuple[str, str]]:
        return {
            (source, target)
            for source, info in self.functions.items()
            for target in info.calls
        }

    def to_json(self) -> dict[str, object]:
        return {
            "nodes": [
                {
                    "id": info.id,
                    "kind": info.kind,
                    "complexity": info.complexity,
                    "trust": info.trust,
                }
                for info in self.functions.values()
            ],
            "edges": [
                {"source": source, "target": target, "kind": "calls", "confidence": "certain"}
                for source, target in sorted(self.call_edges())
            ],
            "module_edges": sorted(self.module_edges()),
        }


def mermaid_id(value: str) -> str:
    return _safe_id(value)


def mermaid_label(value: str) -> str:
    return _escape(value)


def induced_edges(paths: Iterable[list[str]]) -> set[tuple[str, str]]:
    return {
        (path[index], path[index + 1])
        for path in paths
        for index in range(len(path) - 1)
    }
