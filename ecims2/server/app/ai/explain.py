from __future__ import annotations

from typing import Any

from app.ai.features import FEATURE_NAMES


def build_explanation(
    feature_values: dict[str, float],
    feature_means: dict[str, float],
    feature_stds: dict[str, float],
    *,
    top_k: int = 3,
) -> dict[str, Any]:
    contributions: list[dict[str, float | str]] = []

    for name in FEATURE_NAMES:
        value = float(feature_values.get(name, 0.0))
        mean = float(feature_means.get(name, 0.0))
        std = float(feature_stds.get(name, 0.0))
        safe_std = std if std > 1e-9 else 1.0
        deviation = (value - mean) / safe_std
        contributions.append(
            {
                "feature": name,
                "value": value,
                "baseline_mean": mean,
                "baseline_std": std,
                "deviation": deviation,
            }
        )

    top = sorted(contributions, key=lambda item: abs(float(item["deviation"])), reverse=True)[:top_k]
    return {
        "method": "zscore_top_deviation_v1",
        "top_features": top,
        "notes": "Top features ranked by absolute z-score deviation from training baseline.",
    }
