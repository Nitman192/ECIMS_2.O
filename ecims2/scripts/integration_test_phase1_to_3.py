import argparse
import json
import random
import string
import sys
import time
from datetime import datetime, timezone

import requests


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rand_name(prefix: str = "endpoint") -> str:
    suffix = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))
    return f"{prefix}-{suffix}"


def fail(msg: str, detail: object | None = None) -> None:
    print("\nFAIL:", msg)
    if detail is not None:
        try:
            print(json.dumps(detail, indent=2))
        except Exception:
            print(detail)
    sys.exit(1)


def ok(msg: str) -> None:
    print("OK:", msg)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.server_url.rstrip("/")

    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    timeout = 10

    # 1) health
    r = s.get(f"{base}/health", timeout=timeout)
    if r.status_code != 200:
        fail("Health check failed", {"status": r.status_code, "body": r.text})
    ok("/health")

    # 2) register
    name = rand_name()
    hostname = rand_name("host")
    r = s.post(f"{base}/api/v1/agents/register", data=json.dumps({"name": name, "hostname": hostname}), timeout=timeout)
    if r.status_code != 200:
        fail("Agent register failed", {"status": r.status_code, "body": r.text})
    data = r.json()
    agent_id = data.get("agent_id") or data.get("id") or data.get("agent", {}).get("id") or data.get("agent", {}).get("agent_id")
    token = data.get("token") or data.get("agent", {}).get("token")
    if not agent_id or not token:
        fail("Register response missing agent_id/token", data)
    ok(f"register agent_id={agent_id}")

    # 3) heartbeat
    r = s.post(
        f"{base}/api/v1/agents/heartbeat",
        headers={"X-ECIMS-TOKEN": token},
        data=json.dumps({"agent_id": agent_id}),
        timeout=timeout,
    )
    if r.status_code != 200:
        fail("Heartbeat failed", {"status": r.status_code, "body": r.text})
    ok("heartbeat")

    # alerts baseline count
    r = s.get(f"{base}/api/v1/alerts", timeout=timeout)
    if r.status_code != 200:
        fail("Get alerts failed", {"status": r.status_code, "body": r.text})
    before_alerts = r.json()
    before_count = len(before_alerts) if isinstance(before_alerts, list) else 0

    # 4) send 3 events
    file_path = "C:\\\\ecims_integration\\\\a.txt"
    events = [
        {
            "schema_version": "1.0",
            "ts": now_iso(),
            "event_type": "FILE_PRESENT",
            "file_path": file_path,
            "sha256": "a" * 64,
            "details_json": {"source": "integration"},
        },
        {
            "schema_version": "1.0",
            "ts": now_iso(),
            "event_type": "FILE_PRESENT",
            "file_path": file_path,
            "sha256": "b" * 64,
            "details_json": {"source": "integration"},
        },
        {
            "schema_version": "1.0",
            "ts": now_iso(),
            "event_type": "FILE_DELETED",
            "file_path": file_path,
            "sha256": None,
            "details_json": {"source": "integration"},
        },
    ]

    r = s.post(
        f"{base}/api/v1/agents/events",
        headers={"X-ECIMS-TOKEN": token},
        data=json.dumps({"agent_id": agent_id, "events": events}),
        timeout=timeout,
    )
    if r.status_code != 200:
        fail("Events ingestion failed", {"status": r.status_code, "body": r.text})
    ok("events sent")

    # 5) confirm alerts increased
    time.sleep(0.5)
    r = s.get(f"{base}/api/v1/alerts", timeout=timeout)
    if r.status_code != 200:
        fail("Get alerts failed (after events)", {"status": r.status_code, "body": r.text})
    after_alerts = r.json()
    after_count = len(after_alerts) if isinstance(after_alerts, list) else 0
    if after_count < before_count + 3:
        fail("Alerts did not increase by expected delta", {"before": before_count, "after": after_count, "alerts": after_alerts})
    ok("alerts delta >= 3")

    # 6) train AI
    r = s.post(
        f"{base}/api/v1/ai/train",
        data=json.dumps({"model_name": "isolation_forest", "model_version": "1.0", "window_minutes": 60, "start_ts": None, "end_ts": None, "params": {}}),
        timeout=60,
    )
    if r.status_code != 200:
        fail("AI train failed", {"status": r.status_code, "body": r.text})
    train = r.json()
    model_id = train.get("model_id")
    if not model_id:
        fail("Train response missing model_id", train)
    ok(f"ai train model_id={model_id}")

    # 7) score run
    r = s.post(
        f"{base}/api/v1/ai/score/run",
        data=json.dumps({"model_id": model_id, "end_ts": None, "lookback_windows": 1}),
        timeout=60,
    )
    if r.status_code != 200:
        fail("AI score run failed", {"status": r.status_code, "body": r.text})
    ok("ai score run")

    # 8) fetch scores
    r = s.get(f"{base}/api/v1/ai/scores?limit=10", timeout=timeout)
    if r.status_code != 200:
        fail("Fetch AI scores failed", {"status": r.status_code, "body": r.text})
    scores = r.json()
    if not isinstance(scores, list) or len(scores) < 1:
        fail("No AI scores returned", scores)
    ok("ai scores returned")

    print("\nPASS: Phase 1→3 integration succeeded.")
    print(f"- agent_id={agent_id}")
    print(f"- alerts_before={before_count}, alerts_after={after_count}")
    print(f"- model_id={model_id}, scores_count={len(scores)}")


if __name__ == "__main__":
    main()