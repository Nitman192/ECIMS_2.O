from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.database import get_db

FEATURE_SPEC_VERSION = "1.0"
FEATURE_NAMES = [
    "changes_per_hour",
    "unique_files_modified",
    "night_activity_ratio",
    "restart_frequency",
    "baseline_drift_rate",
    "file_change_entropy",
    "delete_events_count",
]


@dataclass
class FeatureRow:
    agent_id: int
    window_start_ts: str
    window_end_ts: str
    features: dict[str, float]


def parse_iso(value: str) -> datetime:
    cleaned = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(cleaned)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _entropy(counter: Counter[str]) -> float:
    total = sum(counter.values())
    if total == 0:
        return 0.0
    ent = 0.0
    for count in counter.values():
        p = count / total
        if p > 0:
            ent -= p * math.log2(p)
    return ent


def _window_bounds(start: datetime, end: datetime, window_minutes: int) -> list[tuple[datetime, datetime]]:
    bounds: list[tuple[datetime, datetime]] = []
    cur = start
    step = timedelta(minutes=window_minutes)
    while cur < end:
        nxt = min(cur + step, end)
        bounds.append((cur, nxt))
        cur = nxt
    return bounds


def build_feature_dataset(window_minutes: int, start_ts: str | None = None, end_ts: str | None = None) -> list[FeatureRow]:
    with get_db() as conn:
        minmax = conn.execute("SELECT MIN(ts) as min_ts, MAX(ts) as max_ts FROM events").fetchone()
        if not minmax or not minmax["min_ts"] or not minmax["max_ts"]:
            return []

        range_start = parse_iso(start_ts) if start_ts else parse_iso(minmax["min_ts"])
        range_end = parse_iso(end_ts) if end_ts else parse_iso(minmax["max_ts"])
        if range_end <= range_start:
            return []

        agent_rows = conn.execute("SELECT id FROM agents ORDER BY id ASC").fetchall()
        agent_ids = [int(r["id"]) for r in agent_rows]
        windows = _window_bounds(range_start, range_end, window_minutes)

        dataset: list[FeatureRow] = []
        for agent_id in agent_ids:
            for win_start, win_end in windows:
                win_start_iso = iso_utc(win_start)
                win_end_iso = iso_utc(win_end)

                event_rows = conn.execute(
                    """
                    SELECT event_type, file_path, ts, details_json
                    FROM events
                    WHERE agent_id = ? AND ts >= ? AND ts < ?
                    """,
                    (agent_id, win_start_iso, win_end_iso),
                ).fetchall()

                alert_rows = conn.execute(
                    """
                    SELECT alert_type
                    FROM alerts
                    WHERE agent_id = ? AND ts >= ? AND ts < ?
                    """,
                    (agent_id, win_start_iso, win_end_iso),
                ).fetchall()

                file_present_paths: list[str] = []
                file_deleted_count = 0
                night_count = 0

                for row in event_rows:
                    event_type = row["event_type"]
                    if event_type == "FILE_PRESENT":
                        file_present_paths.append(row["file_path"])
                    elif event_type == "FILE_DELETED":
                        file_deleted_count += 1

                    hour = parse_iso(row["ts"]).hour
                    if 0 <= hour <= 4:
                        night_count += 1

                total_events = len(event_rows)
                modified_alerts = sum(1 for a in alert_rows if a["alert_type"] == "FILE_MODIFIED")
                path_counter = Counter(file_present_paths)

                features = {
                    "changes_per_hour": float(len(file_present_paths)),
                    "unique_files_modified": float(len(set(file_present_paths))),
                    "night_activity_ratio": float(night_count / total_events) if total_events else 0.0,
                    "restart_frequency": 0.0,  # TODO: derive from richer heartbeat/session telemetry in a future phase.
                    "baseline_drift_rate": float(modified_alerts / total_events) if total_events else 0.0,
                    "file_change_entropy": float(_entropy(path_counter)),
                    "delete_events_count": float(file_deleted_count),
                }

                dataset.append(
                    FeatureRow(
                        agent_id=agent_id,
                        window_start_ts=win_start_iso,
                        window_end_ts=win_end_iso,
                        features=features,
                    )
                )

        return dataset


def serialize_feature_rows(rows: list[FeatureRow]) -> list[dict[str, Any]]:
    return [
        {
            "agent_id": r.agent_id,
            "window_start_ts": r.window_start_ts,
            "window_end_ts": r.window_end_ts,
            "features": r.features,
        }
        for r in rows
    ]


def feature_vector(features: dict[str, float]) -> list[float]:
    return [float(features[name]) for name in FEATURE_NAMES]


def json_dumps_compact(data: Any) -> str:
    return json.dumps(data, separators=(",", ":"), sort_keys=True)
