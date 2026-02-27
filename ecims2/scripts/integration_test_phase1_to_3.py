from __future__ import annotations

import argparse
import random
import string
import sys
from datetime import datetime, timedelta, timezone

import requests


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def rand_suffix(length: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def now_utc_iso(offset_minutes: int = 0) -> str:
    ts = datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)
    return ts.isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="ECIMS integration test across Phase 1->3 APIs")
    parser.add_argument("--server-url", default="http://127.0.0.1:8000", help="Base server URL")
    args = parser.parse_args()

    base = args.server_url.rstrip("/")

    try:
        health_resp = requests.get(f"{base}/health", timeout=10)
    except requests.RequestException as exc:
        fail(f"health request failed: {exc}")

    if health_resp.status_code != 200:
        fail(f"/health returned {health_resp.status_code}: {health_resp.text}")
    print("PASS: /health")

    before_alerts_resp = requests.get(f"{base}/api/v1/alerts?limit=1000", timeout=15)
    if before_alerts_resp.status_code != 200:
        fail(f"could not fetch alerts before test: {before_alerts_resp.status_code} {before_alerts_resp.text}")
    alerts_before = len(before_alerts_resp.json())

    agent_name = f"integration-agent-{rand_suffix()}"
    hostname = f"integration-host-{rand_suffix(6)}"
    register_resp = requests.post(
        f"{base}/api/v1/agents/register",
        json={"name": agent_name, "hostname": hostname},
        timeout=15,
    )
    if register_resp.status_code != 200:
        fail(f"register failed: {register_resp.status_code} {register_resp.text}")
    register_data = register_resp.json()
    agent_id = register_data.get("agent_id")
    token = register_data.get("token")
    if not agent_id or not token:
        fail("register response missing agent_id/token")
    print(f"PASS: register agent_id={agent_id}")

    headers = {"X-ECIMS-TOKEN": token}

    hb_resp = requests.post(
        f"{base}/api/v1/agents/heartbeat",
        headers=headers,
        json={"agent_id": agent_id},
        timeout=15,
    )
    if hb_resp.status_code != 200:
        fail(f"heartbeat failed: {hb_resp.status_code} {hb_resp.text}")
    print("PASS: heartbeat")

    test_path = f"/tmp/ecims-integration-{rand_suffix(6)}.txt"
    hash_a = "a" * 64
    hash_b = "b" * 64

    events_payload = {
        "agent_id": agent_id,
        "events": [
            {
                "schema_version": "1.0",
                "ts": now_utc_iso(0),
                "event_type": "FILE_PRESENT",
                "file_path": test_path,
                "sha256": hash_a,
                "file_size_bytes": 10,
                "mtime_epoch": None,
                "user": "integration",
                "process_name": None,
                "host_ip": None,
                "details_json": {"source": "integration"},
            },
            {
                "schema_version": "1.0",
                "ts": now_utc_iso(1),
                "event_type": "FILE_PRESENT",
                "file_path": test_path,
                "sha256": hash_b,
                "file_size_bytes": 12,
                "mtime_epoch": None,
                "user": "integration",
                "process_name": None,
                "host_ip": None,
                "details_json": {"source": "integration"},
            },
            {
                "schema_version": "1.0",
                "ts": now_utc_iso(2),
                "event_type": "FILE_DELETED",
                "file_path": test_path,
                "sha256": None,
                "file_size_bytes": None,
                "mtime_epoch": None,
                "user": "integration",
                "process_name": None,
                "host_ip": None,
                "details_json": {"source": "integration"},
            },
        ],
    }

    events_resp = requests.post(
        f"{base}/api/v1/agents/events",
        headers=headers,
        json=events_payload,
        timeout=20,
    )
    if events_resp.status_code != 200:
        fail(f"events failed: {events_resp.status_code} {events_resp.text}")
    print("PASS: events (NEW_FILE, FILE_MODIFIED, FILE_DELETED)")

    after_alerts_resp = requests.get(f"{base}/api/v1/alerts?limit=1000", timeout=15)
    if after_alerts_resp.status_code != 200:
        fail(f"could not fetch alerts after event submission: {after_alerts_resp.status_code} {after_alerts_resp.text}")
    alerts_after = len(after_alerts_resp.json())
    if alerts_after < alerts_before + 3:
        fail(f"alerts did not increase by >=3 (before={alerts_before}, after={alerts_after})")
    print("PASS: alert count increased by at least 3")

    train_resp = requests.post(
        f"{base}/api/v1/ai/train",
        json={
            "model_name": "isolation_forest",
            "model_version": "1.0",
            "window_minutes": 60,
            "start_ts": None,
            "end_ts": None,
            "params": {"contamination": 0.1, "random_state": 42},
        },
        timeout=30,
    )
    if train_resp.status_code != 200:
        fail(f"ai train failed: {train_resp.status_code} {train_resp.text}")
    train_data = train_resp.json()
    model_id = train_data.get("model_id")
    if not model_id:
        fail("ai train response missing model_id")
    print(f"PASS: ai train model_id={model_id}")

    score_resp = requests.post(
        f"{base}/api/v1/ai/score/run",
        json={"model_id": model_id, "end_ts": None, "lookback_windows": 1},
        timeout=30,
    )
    if score_resp.status_code != 200:
        fail(f"ai score failed: {score_resp.status_code} {score_resp.text}")
    print("PASS: ai score run")

    scores_resp = requests.get(f"{base}/api/v1/ai/scores?agent_id={agent_id}&limit=20", timeout=15)
    if scores_resp.status_code != 200:
        fail(f"fetch ai scores failed: {scores_resp.status_code} {scores_resp.text}")
    scores = scores_resp.json()
    if len(scores) < 1:
        fail("expected >=1 ai score record")
    print(f"PASS: ai scores fetched ({len(scores)} records)")

    print("PASS: integration_test_phase1_to_3 complete")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("FAIL: interrupted")
        sys.exit(1)
