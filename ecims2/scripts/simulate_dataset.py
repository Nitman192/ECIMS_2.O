from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone

from app.db.database import init_db, get_db


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic ECIMS events for AI evaluation")
    parser.add_argument("--agents", type=int, default=3)
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    init_db()

    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=args.hours)

    with get_db() as conn:
        agent_ids: list[int] = []
        for i in range(args.agents):
            token = f"synthetic-token-{i:04d}"
            cursor = conn.execute(
                "INSERT INTO agents(name, hostname, token, registered_at, last_seen, status) VALUES(?, ?, ?, ?, ?, 'ONLINE')",
                (f"sim-agent-{i+1}", f"sim-host-{i+1}", token, iso(start), iso(now)),
            )
            agent_ids.append(int(cursor.lastrowid))

        for agent_id in agent_ids:
            ts = start
            while ts < now:
                burst = ts.hour in (1, 2) and random.random() > 0.7
                events_count = random.randint(1, 4) if not burst else random.randint(20, 35)
                for j in range(events_count):
                    path = f"/opt/app/file_{random.randint(1, 50)}.cfg"
                    event_type = "FILE_PRESENT" if random.random() > 0.1 else "FILE_DELETED"
                    sha = None if event_type == "FILE_DELETED" else ("%064x" % random.getrandbits(256))
                    conn.execute(
                        "INSERT INTO events(agent_id, ts, event_type, file_path, sha256, details_json) VALUES(?, ?, ?, ?, ?, ?)",
                        (agent_id, iso(ts), event_type, path, sha, json.dumps({"synthetic": True})),
                    )
                    if burst and event_type == "FILE_PRESENT" and random.random() > 0.5:
                        conn.execute(
                            "INSERT INTO alerts(agent_id, ts, alert_type, severity, file_path, previous_sha256, new_sha256, message, status) VALUES(?, ?, 'FILE_MODIFIED', 'RED', ?, ?, ?, ?, 'OPEN')",
                            (agent_id, iso(ts), path, None, sha, "Synthetic modified alert"),
                        )
                ts += timedelta(minutes=10)

    print("Synthetic dataset generated")


if __name__ == "__main__":
    main()
