from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.config import get_settings
from app.db.database import get_db, init_db
from app.ai.service import AIService


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class TestPhase3AI(unittest.TestCase):
    def test_burst_window_has_higher_risk_than_normal_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "phase3_ai.db"
            os.environ["ECIMS_DB_PATH"] = str(db_path)
            os.environ["ECIMS_AI_ARTIFACT_DIR"] = str(Path(temp_dir) / "artifacts")
            get_settings.cache_clear()

            from app import main as main_module

            importlib.reload(main_module)
            init_db()

            now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
            normal_start = now - timedelta(hours=2)
            burst_start = now - timedelta(hours=1)

            with get_db() as conn:
                agent_cur = conn.execute(
                    "INSERT INTO agents(name, hostname, token, registered_at, last_seen, status) VALUES(?, ?, ?, ?, ?, 'ONLINE')",
                    ("ai-agent", "ai-host", "token-ai", _iso(normal_start), _iso(now)),
                )
                agent_id = int(agent_cur.lastrowid)

                for i in range(5):
                    ts = normal_start + timedelta(minutes=i * 10)
                    conn.execute(
                        "INSERT INTO events(agent_id, ts, event_type, file_path, sha256, details_json) VALUES(?, ?, 'FILE_PRESENT', ?, ?, '{}')",
                        (agent_id, _iso(ts), f"/tmp/normal_{i}.txt", "a" * 64),
                    )

                for i in range(60):
                    ts = burst_start + timedelta(minutes=i)
                    conn.execute(
                        "INSERT INTO events(agent_id, ts, event_type, file_path, sha256, details_json) VALUES(?, ?, 'FILE_PRESENT', ?, ?, '{}')",
                        (agent_id, _iso(ts), f"/tmp/burst_{i % 3}.txt", "b" * 64),
                    )
                    if i % 2 == 0:
                        conn.execute(
                            "INSERT INTO alerts(agent_id, ts, alert_type, severity, file_path, previous_sha256, new_sha256, message, status) VALUES(?, ?, 'FILE_MODIFIED', 'RED', ?, ?, ?, ?, 'OPEN')",
                            (agent_id, _iso(ts), f"/tmp/burst_{i % 3}.txt", "a" * 64, "b" * 64, "burst modified"),
                        )

            trained = AIService.train_model(
                model_name="isolation_forest",
                model_version="1.0",
                window_minutes=60,
                start_ts=_iso(normal_start),
                end_ts=_iso(burst_start),
                params={"contamination": 0.1, "random_state": 42},
            )
            AIService.score_agents(model_id=trained["model_id"], end_ts=_iso(now), lookback_windows=2)

            scores = AIService.get_scores(agent_id=agent_id, limit=10)
            self.assertGreaterEqual(len(scores), 2)

            sorted_scores = sorted(scores[:2], key=lambda x: x["window_start_ts"])
            normal_risk = float(sorted_scores[0]["risk_score"])
            burst_risk = float(sorted_scores[1]["risk_score"])
            self.assertGreater(burst_risk, normal_risk)

            get_settings.cache_clear()
            os.environ.pop("ECIMS_DB_PATH", None)
            os.environ.pop("ECIMS_AI_ARTIFACT_DIR", None)


if __name__ == "__main__":
    unittest.main()
