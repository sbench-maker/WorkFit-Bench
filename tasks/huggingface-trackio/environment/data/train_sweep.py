#!/usr/bin/env python3
"""Replay deterministic training observations for the nightly sweep."""

from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path


DATA_DIR = Path(os.environ.get("SWEEP_DATA_DIR", Path(__file__).resolve().parent))


def load_inputs() -> tuple[dict, list[dict]]:
    specs = json.loads((DATA_DIR / "run_specs.json").read_text(encoding="utf-8"))
    with (DATA_DIR / "telemetry.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return specs, rows


def parse_observation(row: dict[str, str]) -> dict[str, object]:
    observation: dict[str, object] = {
        "step": int(row["step"]),
        "timestamp": row["timestamp"],
    }
    for key in ("train_loss", "learning_rate", "grad_norm", "tokens_per_second"):
        observation[key] = float(row[key])
    for key in ("val_loss", "val_accuracy"):
        if row[key] != "":
            observation[key] = float(row[key])
    return observation


def replay_run(spec: dict, rows: list[dict]) -> None:
    """Placeholder loop: add experiment monitoring without changing observations."""
    print(f"starting {spec['run_id']}")
    for raw in rows:
        observation = parse_observation(raw)
        loss = observation["train_loss"]
        shown = "non-finite" if isinstance(loss, float) and not math.isfinite(loss) else f"{loss:.4f}"
        print(f"{spec['run_id']} step={observation['step']} train_loss={shown}")
    print(f"finished {spec['run_id']}")


def main() -> None:
    specs, rows = load_inputs()
    by_run = {
        spec["run_id"]: [row for row in rows if row["run_id"] == spec["run_id"]]
        for spec in specs["runs"]
    }
    for spec in specs["runs"]:
        replay_run(spec, by_run[spec["run_id"]])


if __name__ == "__main__":
    main()
