"""Deterministic BigQuery ML stand-in used only by the local fixture."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from bigframes.pandas import RemoteDataFrame, _record


@dataclass
class _Model:
    model_name: str
    raw_features: list[str]
    encoded_columns: list[str]
    means: np.ndarray
    scales: np.ndarray
    weights: np.ndarray
    training: pd.DataFrame


_MODELS: dict[str, _Model] = {}


def _encode(frame: pd.DataFrame, raw_features: list[str], encoded_columns: list[str] | None = None):
    work = pd.DataFrame(frame[raw_features]).copy()
    for column in raw_features:
        if pd.api.types.is_datetime64_any_dtype(work[column]):
            work[column] = work[column].astype("int64") / 86_400_000_000_000
    encoded = pd.get_dummies(work, dummy_na=True, dtype=float)
    if encoded_columns is not None:
        encoded = encoded.reindex(columns=encoded_columns, fill_value=0.0)
    encoded = encoded.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return encoded


def _probabilities(model: _Model, frame: pd.DataFrame) -> np.ndarray:
    encoded = _encode(frame, model.raw_features, model.encoded_columns)
    x = encoded.to_numpy(dtype=float)
    x = (x - model.means) / model.scales
    design = np.column_stack([np.ones(len(x)), x])
    logits = np.clip(design @ model.weights, -30, 30)
    return 1.0 / (1.0 + np.exp(-logits))


def create_model(
    model_name: str,
    *,
    replace: bool = False,
    options: dict[str, Any] | None = None,
    training_data,
):
    data = pd.DataFrame(training_data).copy()
    if "label" not in data.columns:
        raise ValueError("training_data must contain a label column")
    clean = data.dropna(subset=["label"]).copy()
    y = clean["label"].astype(int).to_numpy(dtype=float)
    if len(set(y.tolist())) < 2:
        raise ValueError("logistic training requires both label classes")
    raw_features = [column for column in clean.columns if column != "label"]
    encoded = _encode(clean, raw_features)
    x = encoded.to_numpy(dtype=float)
    means = x.mean(axis=0)
    scales = x.std(axis=0)
    scales[scales == 0] = 1.0
    x = (x - means) / scales
    design = np.column_stack([np.ones(len(x)), x])
    weights = np.zeros(design.shape[1], dtype=float)
    for _ in range(1800):
        logits = np.clip(design @ weights, -30, 30)
        probs = 1.0 / (1.0 + np.exp(-logits))
        gradient = design.T @ (probs - y) / len(y)
        gradient[1:] += 0.015 * weights[1:]
        weights -= 0.07 * gradient
    model = _Model(
        model_name=model_name,
        raw_features=raw_features,
        encoded_columns=list(encoded.columns),
        means=means,
        scales=scales,
        weights=weights,
        training=clean,
    )
    _MODELS[model_name] = model
    model_type = str((options or {}).get("model_type", "")).upper()
    _record(
        "create_model",
        model_name=model_name,
        replace=bool(replace),
        model_type=model_type,
        training_rows=len(clean),
        label_positive=int(y.sum()),
        label_negative=int(len(y) - y.sum()),
        feature_columns=raw_features,
    )
    return RemoteDataFrame(
        [{"model_name": model_name, "model_type": model_type, "training_rows": len(clean)}]
    )


def evaluate(model_name: str):
    model = _MODELS[model_name]
    y = model.training["label"].astype(int).to_numpy()
    probs = _probabilities(model, model.training)
    clipped = np.clip(probs, 1e-12, 1 - 1e-12)
    log_loss = float(-(y * np.log(clipped) + (1 - y) * np.log(1 - clipped)).mean())
    accuracy = float(((probs >= 0.5).astype(int) == y).mean())
    positives = probs[y == 1]
    negatives = probs[y == 0]
    auc = float(((positives[:, None] > negatives[None, :]).mean()))
    metrics = {
        "model_name": model_name,
        "roc_auc": round(auc, 12),
        "accuracy": round(accuracy, 12),
        "log_loss": round(log_loss, 12),
        "evaluated_rows": int(len(y)),
    }
    _record("evaluate", **metrics)
    return RemoteDataFrame([metrics])


def predict(model_name: str, data):
    model = _MODELS[model_name]
    frame = pd.DataFrame(data).copy()
    probs = _probabilities(model, frame)
    result = frame.copy()
    result["predicted_label"] = probs >= 0.5
    result["predicted_label_probs"] = probs
    _record("predict", model_name=model_name, rows=len(frame), feature_columns=list(frame.columns))
    return RemoteDataFrame(result)

