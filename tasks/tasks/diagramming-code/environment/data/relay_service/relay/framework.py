"""Tiny framework facade that records route metadata without serving traffic."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


def public_route(path: str) -> Callable:
    def decorate(function: Callable) -> Callable:
        function.route_path = path
        function.trust_level = "untrusted"
        return function

    return decorate


def admin_route(path: str) -> Callable:
    def decorate(function: Callable) -> Callable:
        function.route_path = path
        function.trust_level = "authenticated"
        return function

    return decorate


@dataclass
class Request:
    body: str
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)


@dataclass
class Router:
    service_name: str
    handlers: list[Callable[..., Any]] = field(default_factory=list)

    def bind(self, handler: Callable[..., Any]) -> None:
        self.handlers.append(handler)
