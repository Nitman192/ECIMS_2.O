from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM

from app.ai.features import FEATURE_NAMES


@dataclass
class TrainedModelBundle:
    model_name: str
    model_version: str
    model: Any
    feature_means: dict[str, float]
    feature_stds: dict[str, float]
    score_min: float
    score_max: float
    anomaly_cutoff: float
    params: dict[str, Any]


def _feature_stats(matrix: list[list[float]]) -> tuple[dict[str, float], dict[str, float]]:
    cols = list(zip(*matrix)) if matrix else [[] for _ in FEATURE_NAMES]
    means: dict[str, float] = {}
    stds: dict[str, float] = {}
    for idx, name in enumerate(FEATURE_NAMES):
        values = [float(v) for v in cols[idx]] if cols and idx < len(cols) else [0.0]
        mean = statistics.fmean(values) if values else 0.0
        std = statistics.pstdev(values) if len(values) > 1 else 0.0
        means[name] = float(mean)
        stds[name] = float(std)
    return means, stds


def _create_model(model_name: str, params: dict[str, Any]) -> Any:
    if model_name == "isolation_forest":
        merged = {"n_estimators": 100, "contamination": 0.1, "random_state": 42}
        merged.update(params or {})
        return IsolationForest(**merged), merged
    if model_name == "one_class_svm":
        merged = {"kernel": "rbf", "nu": 0.1, "gamma": "scale"}
        merged.update(params or {})
        return OneClassSVM(**merged), merged
    raise ValueError(f"Unsupported model_name: {model_name}")


def train_bundle(model_name: str, model_version: str, X: list[list[float]], params: dict[str, Any]) -> TrainedModelBundle:
    if not X:
        raise ValueError("No feature rows available for training")

    model, merged_params = _create_model(model_name, params)
    matrix = np.array(X, dtype=float)
    model.fit(matrix)

    train_scores = model.score_samples(matrix)
    score_min = float(np.percentile(train_scores, 5))
    score_max = float(np.percentile(train_scores, 95))
    if score_max <= score_min:
        score_max = score_min + 1e-6

    anomaly_cutoff = float(np.percentile(train_scores, 10))
    means, stds = _feature_stats(X)

    return TrainedModelBundle(
        model_name=model_name,
        model_version=model_version,
        model=model,
        feature_means=means,
        feature_stds=stds,
        score_min=score_min,
        score_max=score_max,
        anomaly_cutoff=anomaly_cutoff,
        params=merged_params,
    )


def save_bundle(path: str, bundle: TrainedModelBundle) -> None:
    payload = {
        "model_name": bundle.model_name,
        "model_version": bundle.model_version,
        "model": bundle.model,
        "feature_means": bundle.feature_means,
        "feature_stds": bundle.feature_stds,
        "score_min": bundle.score_min,
        "score_max": bundle.score_max,
        "anomaly_cutoff": bundle.anomaly_cutoff,
        "params": bundle.params,
        "feature_names": FEATURE_NAMES,
    }
    joblib.dump(payload, path)


def load_bundle(path: str) -> dict[str, Any]:
    return joblib.load(path)


def score_to_risk(score: float, score_min: float, score_max: float) -> float:
    span = max(score_max - score_min, 1e-6)
    normalized = (score_max - score) / span
    risk = max(0.0, min(100.0, normalized * 100.0))
    return float(risk)
