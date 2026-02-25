from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

from app.ai.service import AIService
from app.db.database import get_db, init_db


def compute_metrics(y_true: list[int], y_pred: list[int]) -> dict[str, float]:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fpr,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ECIMS Phase 3 AI anomaly scoring")
    parser.add_argument("--window-minutes", type=int, default=60)
    parser.add_argument("--output", default="ai_eval_report.json")
    args = parser.parse_args()

    init_db()

    now = datetime.now(timezone.utc)
    train_end = now - timedelta(hours=4)
    train_start = train_end - timedelta(days=2)

    trained = AIService.train_model(
        model_name="isolation_forest",
        model_version="1.0",
        window_minutes=args.window_minutes,
        start_ts=train_start.isoformat(),
        end_ts=train_end.isoformat(),
        params={"contamination": 0.1, "random_state": 42},
    )

    AIService.score_agents(
        model_id=trained["model_id"],
        end_ts=now.isoformat(),
        lookback_windows=6,
    )

    with get_db() as conn:
        rows = conn.execute(
            "SELECT agent_id, window_end_ts, is_anomaly, risk_score FROM ai_scores ORDER BY window_end_ts ASC"
        ).fetchall()

    y_true: list[int] = []
    y_pred: list[int] = []
    for row in rows:
        end_hour = datetime.fromisoformat(row["window_end_ts"].replace("Z", "+00:00")).hour
        truth = 1 if end_hour in (1, 2) else 0
        y_true.append(truth)
        y_pred.append(int(row["is_anomaly"]))

    metrics = compute_metrics(y_true, y_pred)
    report = {
        "trained_model": trained,
        "samples_scored": len(rows),
        "metrics": metrics,
    }

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
