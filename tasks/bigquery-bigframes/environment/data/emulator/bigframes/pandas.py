"""A deliberately small BigFrames DataFrame emulator backed by local pandas."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd


def fixture_root() -> Path:
    return Path(os.environ.get("BIGFRAMES_FIXTURE_ROOT", "/root/data"))


def results_root() -> Path:
    return Path(os.environ.get("BIGFRAMES_RESULTS_ROOT", "/root/results"))


def trace_path() -> Path:
    return Path(os.environ.get("BIGFRAMES_TRACE_PATH", str(results_root() / "bigframes_trace.json")))


def _load_trace() -> list[dict[str, Any]]:
    path = trace_path()
    if not path.is_file():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _record(event: str, **details: Any) -> None:
    path = trace_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = _load_trace()
    rows.append({"event": event, **details})
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


class RemoteSeries(pd.Series):
    @property
    def _constructor(self):
        return RemoteSeries

    @property
    def _constructor_expanddim(self):
        return RemoteDataFrame

    def peek(self, n: int = 5):
        _record("peek", kind="series", rows=min(n, len(self)))
        return pd.Series(self.iloc[:n].copy())

    def to_pandas(self):
        _record("materialize", kind="series", rows=len(self))
        return pd.Series(self.copy())


class RemoteDataFrame(pd.DataFrame):
    _metadata = ["_source_table"]

    @property
    def _constructor(self):
        return RemoteDataFrame

    @property
    def _constructor_sliced(self):
        return RemoteSeries

    def peek(self, n: int = 5):
        _record("peek", kind="dataframe", rows=min(n, len(self)))
        return pd.DataFrame(self.iloc[:n].copy())

    def head(self, n: int = 5):
        _record("head", kind="dataframe", rows=min(n, len(self)))
        return super().head(n)

    def to_pandas(self):
        _record(
            "materialize",
            kind="dataframe",
            rows=len(self),
            source_table=getattr(self, "_source_table", None),
        )
        return pd.DataFrame(self.copy())

    def merge(self, *args, **kwargs):
        right = args[0] if args else kwargs.get("right")
        _record("merge", left_rows=len(self), right_rows=len(right) if right is not None else None)
        return super().merge(*args, **kwargs)

    def join(self, *args, **kwargs):
        other = args[0] if args else kwargs.get("other")
        _record("join", left_rows=len(self), right_rows=len(other) if other is not None else None)
        return super().join(*args, **kwargs)

    def groupby(self, *args, **kwargs):
        _record("groupby", rows=len(self), by=str(args[0] if args else kwargs.get("by")))
        return super().groupby(*args, **kwargs)

    def drop_duplicates(self, *args, **kwargs):
        _record("drop_duplicates", rows=len(self), subset=str(kwargs.get("subset", args[0] if args else None)))
        return super().drop_duplicates(*args, **kwargs)


class _BigQueryOptions:
    def __init__(self) -> None:
        self._ordering_mode: str | None = None
        self.project: str | None = None

    @property
    def ordering_mode(self) -> str | None:
        return self._ordering_mode

    @ordering_mode.setter
    def ordering_mode(self, value: str) -> None:
        self._ordering_mode = value
        _record("ordering_mode", value=value)


class _Options:
    def __init__(self) -> None:
        self.bigquery = _BigQueryOptions()


options = _Options()


def read_gbq(table: str, *args, **kwargs) -> RemoteDataFrame:
    if not isinstance(table, str):
        raise TypeError("table must be a BigQuery table ID")
    looks_like_sql = any(token in table.lower() for token in ("select ", " from ", " where "))
    _record("read_gbq", table=table, raw_sql=looks_like_sql)
    if looks_like_sql:
        raise ValueError("The offline fixture accepts table IDs, not raw SQL")
    catalog = json.loads((fixture_root() / "catalog.json").read_text(encoding="utf-8"))
    if table not in catalog:
        raise KeyError(f"Unknown fixture table: {table}")
    path = fixture_root() / catalog[table]
    frame = pd.read_csv(path)
    for column in ("signup_date", "month", "last_activity_date", "ingested_at", "opened_at"):
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column])
    if "is_internal" in frame.columns:
        frame["is_internal"] = frame["is_internal"].astype(str).str.lower().eq("true")
    if "churned_next_30d" in frame.columns:
        frame["churned_next_30d"] = pd.to_numeric(frame["churned_next_30d"], errors="coerce").astype("Int64")
    result = RemoteDataFrame(frame)
    result._source_table = table
    return result


def concat(objs, *args, **kwargs) -> RemoteDataFrame:
    _record("concat", frames=len(objs))
    return RemoteDataFrame(pd.concat(objs, *args, **kwargs))


def to_datetime(arg, *args, **kwargs):
    return pd.to_datetime(arg, *args, **kwargs)


def to_timedelta(arg, *args, **kwargs):
    return pd.to_timedelta(arg, *args, **kwargs)


DataFrame = RemoteDataFrame
Series = RemoteSeries
