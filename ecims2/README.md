# ECIMS 2.0 (Phase 1 + Phase 2)

Endpoint Configuration Integrity Monitoring System for offline/LAN deployment.

## Folder Structure

```text
ecims2/
  server/
    app/
      main.py
      api/
      core/
      db/
      models/
      services/
      schemas/
      utils/
    tests/
    requirements.txt
  agent/
    ecims_agent/
      main.py
      scanner.py
      api_client.py
      config.py
      storage.py
      hashing.py
    requirements.txt
  shared/
    schemas/
  docs/
    02_Threat_Model.docx
    Phase_1_Core_Monitoring.md
  configs/
    server.yaml
    agent.yaml
  scripts/
    init_db.py
    run_server.sh
  offline_bundle/
    wheelhouse/
    requirements_server.lock.txt
    requirements_agent.lock.txt
    build_wheels.sh
    build_wheels.bat
    install_offline.sh
    install_offline.bat
  README.md
```

## Setup

### 1) Server setup
```bash
cd ecims2
python -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.txt
```

### 2) Agent setup
```bash
cd ecims2
source .venv/bin/activate
pip install -r agent/requirements.txt
```

## Run Tests

```bash
cd ecims2
source .venv/bin/activate
PYTHONPATH=server python -m unittest server.tests.test_phase1_smoke server.tests.test_phase2_controls server.tests.test_phase3_ai -v
```

Tests use temporary SQLite files via `ECIMS_DB_PATH` so real `ecims2.db` is not touched.


## Dependency Notes

- Server configuration loading depends on **PyYAML** (`import yaml`).
- `PyYAML` is explicitly included in `server/requirements.txt` and the offline wheelhouse workflow.
- After any dependency change, refresh offline artifacts on an internet-connected machine:

```bash
cd ecims2
./offline_bundle/build_wheels.sh
```

Windows:
```bat
cd ecims2
offline_bundle\build_wheels.bat
```


## Integration Test (Phase 1 -> 3)

Run end-to-end integration checks against a running server:

```bash
cd ecims2
source .venv/bin/activate
python scripts/integration_test_phase1_to_3.py --server-url http://127.0.0.1:8000
```

This script validates:
1. `GET /health`
2. Agent register + heartbeat
3. Event pipeline (`NEW_FILE`, `FILE_MODIFIED`, `FILE_DELETED`)
4. Alert count increase check
5. AI train + score run
6. AI scores retrieval (`>=1` expected)

Dependency note: server configuration loading requires **PyYAML** (`import yaml`) and the integration test script requires **requests**.

After dependency changes, refresh the offline wheelhouse on an internet-connected machine:

```bash
cd ecims2
./offline_bundle/build_wheels.sh
```

Windows:
```bat
cd ecims2
offline_bundle\build_wheels.bat
```

## Offline Install (Air-gapped)

### A) On an internet-connected machine
```bash
cd ecims2
./offline_bundle/build_wheels.sh
```

Windows:
```bat
cd ecims2
offline_bundle\build_wheels.bat
```

### B) On an offline machine
```bash
cd ecims2
./offline_bundle/install_offline.sh
```

Windows:
```bat
cd ecims2
offline_bundle\install_offline.bat
```

## Run Server

```bash
cd ecims2
source .venv/bin/activate
./scripts/run_server.sh
```

## Run Agent

```bash
cd ecims2
source .venv/bin/activate
PYTHONPATH=agent python -m ecims_agent.main --config configs/agent.yaml
```

## API Endpoints

### Existing Phase 1
- `POST /api/v1/agents/register`
- `POST /api/v1/agents/heartbeat`
- `POST /api/v1/agents/events`
- `GET /api/v1/alerts`
- `GET /api/v1/agents`
- `POST /api/v1/admin/run_offline_check`
- `GET /health`

### Phase 2 additions
- `POST /api/v1/admin/baseline/approve`
- `POST /api/v1/admin/retention/run`

## Phase 2 Event Schema (Frozen v1)

Server canonical timestamp format is **UTC ISO-8601** (`datetime.isoformat()` with timezone).

Each event should include:
- `schema_version` = `"1.0"`
- `ts`
- `event_type` (`FILE_PRESENT` or `FILE_DELETED`)
- `file_path` (normalized)
- `sha256` (required for `FILE_PRESENT`, optional for `FILE_DELETED`)
- Optional: `file_size_bytes`, `mtime_epoch`, `user`, `process_name`, `host_ip`, `details_json`

If `allow_legacy_phase1_events=true`, Phase 1 event payloads are accepted and normalized to v1 internally (audit logged as `LEGACY_EVENT_ACCEPTED`).

## Example: v1 event payload

```bash
curl -X POST http://127.0.0.1:8000/api/v1/agents/events \
  -H "Content-Type: application/json" \
  -H "X-ECIMS-TOKEN: <token>" \
  -d '{
    "agent_id": 1,
    "events": [
      {
        "schema_version": "1.0",
        "ts": "2026-01-01T00:00:00Z",
        "event_type": "FILE_PRESENT",
        "file_path": "/tmp/sample.txt",
        "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "file_size_bytes": 128,
        "mtime_epoch": 1735689600.0,
        "user": "SYSTEM",
        "process_name": null,
        "host_ip": null,
        "details_json": {"source":"manual"}
      }
    ]
  }'
```

## Example: manual baseline approval (MANUAL mode)

```bash
curl -X POST http://127.0.0.1:8000/api/v1/admin/baseline/approve \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": 1,
    "file_path": "/tmp/sample.txt",
    "approve_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "reason": "Change approved during patch window"
  }'
```

## Example: retention run

```bash
curl -X POST http://127.0.0.1:8000/api/v1/admin/retention/run
```

## Security & Audit Notes
- Per-agent token is required for heartbeat and event APIs.
- Audit trail table `audit_log` records key actions: registrations, baseline create/update/approval, alerts, offline checks, and retention runs.
- Retention windows are configurable in `configs/server.yaml`.


## Phase 3 AI Anomaly Detection

Phase 3 adds explainable anomaly scoring on top of rule-based alerts. Rule alerts are unchanged and remain primary detections.

### Feature Spec v1.0 (rolling window)
- `changes_per_hour`
- `unique_files_modified`
- `night_activity_ratio` (UTC 00:00-05:00 ratio)
- `restart_frequency` (currently `0.0`, TODO for richer telemetry)
- `baseline_drift_rate`
- `file_change_entropy`
- `delete_events_count`

### AI endpoints
- `POST /api/v1/ai/train`
- `POST /api/v1/ai/score/run`
- `GET /api/v1/ai/scores`
- `GET /api/v1/ai/models`

### Train model example
```bash
curl -X POST http://127.0.0.1:8000/api/v1/ai/train   -H "Content-Type: application/json"   -d '{
    "model_name": "isolation_forest",
    "model_version": "1.0",
    "window_minutes": 60,
    "start_ts": null,
    "end_ts": null,
    "params": {"contamination": 0.1, "random_state": 42}
  }'
```

### Run scoring example
```bash
curl -X POST http://127.0.0.1:8000/api/v1/ai/score/run   -H "Content-Type: application/json"   -d '{
    "model_id": 1,
    "end_ts": null,
    "lookback_windows": 1
  }'
```

### Fetch scores/models
```bash
curl "http://127.0.0.1:8000/api/v1/ai/scores?limit=50"
curl "http://127.0.0.1:8000/api/v1/ai/scores?agent_id=1&limit=20"
curl "http://127.0.0.1:8000/api/v1/ai/models"
```

### Evaluation harness scripts
```bash
cd ecims2
source .venv/bin/activate
PYTHONPATH=server python scripts/simulate_dataset.py --agents 3 --hours 24
PYTHONPATH=server python scripts/evaluate_ai.py --window-minutes 60 --output ai_eval_report.json
```
