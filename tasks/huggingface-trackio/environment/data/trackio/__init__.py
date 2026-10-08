"""Small offline-compatible Trackio surface for the bundled exercise.

It intentionally models projects, runs, metric logs, alerts, and finalization,
while never contacting a remote service.
"""

from __future__ import annotations

from enum import Enum
import json
import math
import os
from pathlib import Path
from typing import Any


class AlertLevel(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


_active: dict[str, Any] | None = None


def _db_path() -> Path:
    return Path(os.environ.get("TRACKIO_DB_PATH", "/root/results/trackio_store.json"))


def _read_store() -> dict[str, Any]:
    path = _db_path()
    if not path.exists():
        return {"schema_version": "offline-1", "projects": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_store(store: dict[str, Any]) -> None:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    return value


def init(
    *,
    project: str,
    name: str | None = None,
    config: dict[str, Any] | None = None,
    group: str | None = None,
    space_id: str | None = None,
    private: bool | None = None,
    webhook_url: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Start or replace a named local run."""
    global _active
    if space_id or webhook_url:
        raise RuntimeError("offline fixture forbids remote sync and webhooks")
    if _active is not None:
        finish()
    run_name = name or "run"
    store = _read_store()
    project_row = store["projects"].setdefault(project, {"runs": {}})
    project_row["runs"][run_name] = {
        "config": _safe(config or {}),
        "group": group,
        "private": private,
        "logs": [],
        "alerts": [],
        "finished": False,
    }
    _write_store(store)
    _active = {"project": project, "run": run_name, "next_step": 0, "last_step": None, "last_timestamp": None}
    return dict(_active)


def log(
    values: dict[str, Any],
    *,
    step: int | None = None,
    timestamp: str | None = None,
    **_: Any,
) -> None:
    """Append one structured metric observation to the active run."""
    global _active
    if _active is None:
        raise RuntimeError("trackio.init() must be called before log()")
    payload = dict(values)
    event_step = step if step is not None else payload.pop("step", _active["next_step"])
    timestamp = timestamp if timestamp is not None else payload.pop("timestamp", None)
    store = _read_store()
    run = store["projects"][_active["project"]]["runs"][_active["run"]]
    run["logs"].append({"step": int(event_step), "timestamp": timestamp, "metrics": _safe(payload)})
    _write_store(store)
    _active["last_step"] = int(event_step)
    _active["last_timestamp"] = timestamp
    _active["next_step"] = max(int(event_step) + 1, int(_active["next_step"]))


def alert(
    title: str,
    text: str = "",
    level: AlertLevel | str = AlertLevel.WARN,
    webhook_url: str | None = None,
    **_: Any,
) -> None:
    """Persist an alert at the most recently logged step."""
    if _active is None:
        raise RuntimeError("trackio.init() must be called before alert()")
    if webhook_url:
        raise RuntimeError("offline fixture forbids webhooks")
    raw_level = level.value if isinstance(level, AlertLevel) else str(level).lower()
    if raw_level not in {"info", "warn", "error"}:
        raise ValueError(f"unsupported alert level: {level}")
    store = _read_store()
    run = store["projects"][_active["project"]]["runs"][_active["run"]]
    run["alerts"].append(
        {
            "run": _active["run"],
            "title": str(title),
            "text": str(text),
            "level": raw_level,
            "step": _active["last_step"],
            "timestamp": _active["last_timestamp"],
        }
    )
    _write_store(store)


def finish() -> None:
    """Finalize the active run."""
    global _active
    if _active is None:
        return
    store = _read_store()
    store["projects"][_active["project"]]["runs"][_active["run"]]["finished"] = True
    _write_store(store)
    _active = None


def show(*_: Any, **__: Any) -> None:
    """Dashboard placeholder: the queryable local store is the offline dashboard source."""
    return None


def sync(*_: Any, **__: Any) -> None:
    raise RuntimeError("offline fixture forbids remote sync")
