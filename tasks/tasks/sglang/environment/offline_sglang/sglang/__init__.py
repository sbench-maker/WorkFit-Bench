"""A tiny deterministic SGLang-compatible runtime for an offline benchmark fixture.

It intentionally implements only the program, constrained generation, batch, and
prefix-cache observation surfaces exercised by this task.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Union


__version__ = "1.0.0"
_LAST_BATCH_METRICS: dict[str, Any] = {}


@dataclass(frozen=True)
class Generation:
    name: str
    max_tokens: int = 256
    json_schema: Optional[dict[str, Any]] = None
    regex: Optional[str] = None
    grammar: Optional[str] = None
    temperature: float = 0.0


def gen(name: str, **kwargs: Any) -> Generation:
    return Generation(name=name, **{key: value for key, value in kwargs.items() if key in Generation.__dataclass_fields__})


def _json_after(prompt: str, marker: str) -> Any:
    offset = prompt.rfind(marker)
    if offset < 0:
        raise ValueError(f"prompt is missing required marker {marker}")
    raw = prompt[offset + len(marker):].lstrip()
    return json.JSONDecoder().raw_decode(raw)[0]


def _route(policy: dict[str, Any], ticket: dict[str, Any]) -> tuple[dict[str, Any], str]:
    text = f"{ticket.get('subject', '')} {ticket.get('body', '')}".casefold()
    selected = None
    phrase = None
    for rule in policy.get("rules", []):
        for candidate in rule.get("any_phrases", []):
            if str(candidate).casefold() in text:
                selected = rule
                phrase = str(candidate)
                break
        if selected is not None:
            break
    if selected is None:
        selected = dict(policy["fallback"])
        selected.setdefault("id", selected.get("rule_id", "fallback"))
        phrase = "no listed escalation phrase"
    decision = {
        "ticket_id": str(ticket.get("ticket_id", "")),
        "rule_id": str(selected.get("id", selected.get("rule_id", "fallback"))),
        "category": selected["category"],
        "priority": selected["priority"],
        "team": selected["team"],
        "requires_human": bool(selected["requires_human"]),
        "action": selected["action"],
        "reason": f"Matched '{phrase}' under rule {selected.get('id', selected.get('rule_id', 'fallback'))}.",
    }
    return decision, phrase


def _validate(value: Any, schema: Optional[dict[str, Any]]) -> None:
    if not schema:
        return
    expected_type = schema.get("type")
    if expected_type == "object" and not isinstance(value, dict):
        raise ValueError("generated value is not an object")
    for key in schema.get("required", []):
        if key not in value:
            raise ValueError(f"generated value is missing required property {key}")
    for key, spec in schema.get("properties", {}).items():
        if key not in value:
            continue
        item = value[key]
        kind = spec.get("type")
        valid = {
            "string": isinstance(item, str),
            "boolean": isinstance(item, bool),
            "integer": isinstance(item, int) and not isinstance(item, bool),
            "number": isinstance(item, (int, float)) and not isinstance(item, bool),
            "object": isinstance(item, dict),
            "array": isinstance(item, list),
        }.get(kind, True)
        if not valid:
            raise ValueError(f"property {key} does not match schema type {kind}")
        if "enum" in spec and item not in spec["enum"]:
            raise ValueError(f"property {key} is outside its enum")


class State(dict[str, Any]):
    def __init__(self) -> None:
        super().__init__()
        self.prompt = ""
        self.generations: list[dict[str, Any]] = []

    def __iadd__(self, value: Union[str, Generation]) -> "State":
        if isinstance(value, str):
            self.prompt += value
            return self
        if not isinstance(value, Generation):
            raise TypeError("state accepts strings or gen() results")
        try:
            policy = _json_after(self.prompt, "POLICY_JSON:")
            ticket = _json_after(self.prompt, "TICKET_JSON:")
            decision, _ = _route(policy, ticket)
            _validate(decision, value.json_schema)
            rendered = json.dumps(decision, ensure_ascii=False, separators=(",", ":"))
            schema_failure = 0
        except Exception:
            schema_failure = 1
            raise
        self[value.name] = rendered
        self.generations.append(
            {
                "name": value.name,
                "constraint": "json_schema" if value.json_schema is not None else "unconstrained",
                "schema_validation_failures": schema_failure,
            }
        )
        self.prompt += rendered
        return self


@dataclass(frozen=True)
class BoundProgram:
    program: "Program"
    kwargs: dict[str, Any]

    def run(self) -> State:
        return self.program.run(**self.kwargs)


class Program:
    def __init__(self, callback: Callable[..., Any]) -> None:
        self.callback = callback
        self.__name__ = getattr(callback, "__name__", "program")

    def run(self, **kwargs: Any) -> State:
        state = State()
        self.callback(state, **kwargs)
        return state

    def bind(self, **kwargs: Any) -> BoundProgram:
        return BoundProgram(self, kwargs)


def function(callback: Callable[..., Any]) -> Program:
    return Program(callback)


def _lcp(left: str, right: str) -> int:
    limit = min(len(left), len(right))
    index = 0
    while index < limit and left[index] == right[index]:
        index += 1
    return index


def run_batch(calls: list[BoundProgram]) -> list[State]:
    global _LAST_BATCH_METRICS
    states = [call.run() for call in calls]
    prompts = [state.prompt for state in states]
    hits = [0]
    for previous, current in zip(prompts, prompts[1:]):
        hits.append(_lcp(previous, current))
    total = sum(len(prompt) for prompt in prompts)
    hit_total = sum(hits)
    generations = [item for state in states for item in state.generations]
    failures = sum(item["schema_validation_failures"] for item in generations)
    constrained = sum(item["constraint"] == "json_schema" for item in generations)
    _LAST_BATCH_METRICS = {
        "requests": len(states),
        "constrained_requests": constrained,
        "schema_validation_failures": failures,
        "prompt_chars": total,
        "cache_hit_chars": hit_total,
        "cache_hit_rate": round(hit_total / total, 6) if total else 0.0,
    }
    trace_path = os.environ.get("SGLANG_TRACE_PATH")
    if trace_path:
        trace = dict(_LAST_BATCH_METRICS)
        trace["prompt_sha256"] = [hashlib.sha256(prompt.encode("utf-8")).hexdigest() for prompt in prompts]
        trace["constraint_kinds"] = [item["constraint"] for item in generations]
        Path(trace_path).write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
    return states


def get_last_batch_metrics() -> dict[str, Any]:
    return dict(_LAST_BATCH_METRICS)


def set_default_backend(backend: Any) -> None:
    del backend


class Offline:
    def __init__(self, *_: Any, **__: Any) -> None:
        pass
