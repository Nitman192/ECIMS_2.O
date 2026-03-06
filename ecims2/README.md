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
PYTHONPATH=server python -m unittest server.tests.test_phase1_smoke server.tests.test_phase2_controls server.tests.test_phase3_ai server.tests.test_phase4_license server.tests.test_crypto_dependency -v
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

Parallel/local multi-agent run with isolated runtime state:

```bash
cd ecims2
source .venv/bin/activate
PYTHONPATH=agent python -m ecims_agent.main --config configs/agent.local.dev.yaml --runtime-id client-a --state-dir .ecims_agent_runtime
PYTHONPATH=agent python -m ecims_agent.main --config configs/agent.local.dev.yaml --runtime-id client-b --state-dir .ecims_agent_runtime
```

## API Endpoints

### Existing Phase 1
- `POST /api/v1/agents/register`
- `POST /api/v1/agents/heartbeat`
- `POST /api/v1/agents/events`
- `GET /api/v1/alerts`
- `GET /api/v1/agents`
- `GET /api/v1/agents/{agent_id}/self/status`
- `GET /api/v1/admin/agents/{agent_id}/self-status`
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



## Phase 4 Offline Licensing (RSA)

ECIMS enforces an offline RSA-signed license on startup.

### Signature scheme
- Verification accepts **RSA-PSS + SHA256** (preferred) and **PKCS1v15 + SHA256** (legacy compatibility).
- License authority now signs with **RSA-PSS** by default.

### License config
- `license_path` (default: `configs/license.ecims`)
- `license_public_key_path` (default: `server/app/license/public_key.pem`)
- Environment overrides:
  - `ECIMS_LICENSE_PATH`
  - `ECIMS_LICENSE_PUBLIC_KEY_PATH`

### Optional machine binding
License payload can include `machine_fingerprint` (SHA256 hex). If present and not matching local machine, license is invalid with `MACHINE_MISMATCH`.

### Rollback tamper protection
Server persists a signed last-run timestamp under `server/.ecims_state/last_run.json`. If system time appears rolled back beyond 5 minutes tolerance, license is invalid with `TAMPER_DETECTED`.

### License status endpoint
- `GET /api/v1/license/status`

Fields include:
- `is_valid`, `reason`, `loaded_at_utc`
- `license_id`, `customer_name`, `org_name`
- `expiry_date`, `ai_enabled`, `max_agents`, `agents_registered`
- `machine_match`, `local_fingerprint_short`

### Gating behavior
- Agent registration is blocked with `403` when:
  - license is invalid/expired/tamper-detected
  - registered agents reached `max_agents`
- AI endpoints (`/api/v1/ai/*`) are blocked with `403` when:
  - license is invalid/expired/tamper-detected
  - `ai_enabled` is false

### License authority tools
Use the offline tools under `license_authority/`:

```bash
cd license_authority
python generate_keys.py
python generate_license.py   --org-name "ACME"   --max-agents 100   --expiry-date 2030-12-31   --ai-enabled true   --license-id "LIC-2030-0001"   --customer-name "ACME"   --out ../ecims2/configs/license.ecims
```

Copy generated `public_key.pem` to `ecims2/server/app/license/public_key.pem`.



## Phase 4.5 Defense Hardened Build

### Standard build vs defense build
- **Standard build**: pure Python modules, easiest for development/testing.
- **Defense build**: compiles `app/licensing_core` with Nuitka, embeds public key in code, and supports removing licensing source `.py` from distribution.

### Hardened build steps

```bash
cd ecims2
source .venv/bin/activate
pip install nuitka
python scripts/build_hardened.py --output-dir build/hardened
```

Notes:
- The hardened licensing module avoids runtime file-based public key loading by default.
- Integrity checks include runtime SHA256 verification of licensing core source in standard mode and tamper detection hooks for hardened deployments.
- Build remains fully offline (no network validation).

## Phase 6: Agent↔Server mTLS + Offline Provisioning

### Server configuration (`configs/server.yaml`)

- `mtls_enabled`, `mtls_required`
- `server_cert_path`, `server_key_path`
- `client_ca_cert_path`
- `tls_min_version` (`1.3` strict default; `1.2` only when policy allows)
- `security_policy_path`, `security_policy_sig_path`

`STRICT` policy defaults enforce:
- `mtls_required=true`
- `pinning_required=true`
- `allow_tls12=false`
- `allow_plain_https=false`

### Agent configuration (`configs/agent.yaml`)

- mTLS identity via PEM pair or PFX:
  - `agent_client_cert_path` + `agent_client_key_path`
  - or `agent_pfx_path` + `agent_pfx_password`
- server trust/pinning:
  - `server_ca_bundle_path`
  - `server_cert_pin_sha256`

### End-to-end offline flow

1. Generate CA on authority host:
   - `python license_authority/generate_mtls_ca.py --out-dir ./ca`
2. Generate server cert signed by the CA (can be done with OpenSSL or your PKI tooling).
3. Agent generates CSR locally:
   - `python agent/ecims_agent/agent_generate_csr.py --agent-id 101 --out-dir ./agent101`
4. Sign CSR offline:
   - `python license_authority/sign_agent_csr.py --ca-key ./ca/mtls_ca.key --ca-cert ./ca/mtls_ca.crt --csr ./agent101/agent_101.csr --agent-id 101 --out-cert ./agent101/agent_101.crt`
5. Install agent cert/key (or PFX) on endpoint.
6. Start server with TLS + client cert validation:
   - `./scripts/run_server_tls.sh`

### mTLS identity enforcement

- Server expects agent identity from client cert `CN=<agent_id>` or SAN URI `urn:ecims:agent:<agent_id>`.
- Agent request payload `agent_id` must match cert identity.
- Audit actions on failure:
  - `MTLS_MISSING_CERT`
  - `MTLS_INVALID_CERT`
  - `MTLS_AGENT_MISMATCH`

### Integration test scaffold

A scaffold test is included for future TLS-enabled CI and is skipped when local cert tooling/runtime setup is unavailable.

## Phase 6.1: Agent certificate revocation (DB-based)

- Agent records now include revocation flags in DB (`agent_revoked`, `revoked_at`, `revocation_reason`).
- Revoked agents are blocked in mTLS identity enforcement with `403 Agent certificate revoked` and audited as `MTLS_AGENT_REVOKED`.
- Admin endpoints (license-gated + token-protected via `X-ECIMS-ADMIN-TOKEN`) are available:
  - `POST /api/v1/admin/agents/{agent_id}/revoke` body: `{ "reason": "..." }`
  - `POST /api/v1/admin/agents/{agent_id}/restore`
- Agent list includes non-sensitive `agent_revoked` status; revocation reason/timestamp stay internal.

Migration utility:

```bash
python scripts/migrate_phase61_revocation.py
```

## Server Capability Snapshot (Current)

The FastAPI server currently includes:
- JWT auth + RBAC (`ADMIN`/`ANALYST`/`VIEWER`) with `/auth/login` and `/auth/me`.
- mTLS identity validation for agent ingestion (`/agents/register`, `/agents/heartbeat`, `/agents/events`).
- Offline license verification with startup validation and runtime status endpoint.
- Signed security policy loading and status reporting (`/security/status`).
- AI model train/score/list endpoints with license gating.
- Admin controls for revocation, baseline approval, retention, and audit API read/export.

## Production Hardening Checklist

Before running in production (`ECIMS_ENVIRONMENT=prod` or `test`):
1. Set a strong `ECIMS_JWT_SECRET` (not default, minimum 24+ chars).
2. Provide explicit bootstrap admin values when first user DB is empty:
   - `ECIMS_BOOTSTRAP_ADMIN_TOKEN`
   - `ECIMS_BOOTSTRAP_ADMIN_USERNAME`
   - `ECIMS_BOOTSTRAP_ADMIN_PASSWORD`
3. Ensure signed security policy artifacts are present and valid:
   - `configs/security.policy.json`
   - `configs/security.policy.sig`
   - `configs/security.policy.public.pem`
4. Run TLS/mTLS mode with `mtls_enabled=true` and `mtls_required=true` unless in controlled development.
5. Configure endpoint throttling:
   - login: `ECIMS_LOGIN_RATE_LIMIT_*`
   - agent ingest: `ECIMS_AGENT_RATE_LIMIT_*`

## Device Control Foundation (Architecture + Contracts)

Phase adds server-side contracts only (no OS enforcement yet) for USB mass-storage control.

### Security policy schema additions

`configs/security.policy.json` now supports:
- `mass_storage_default_action`: `block_on_insert | allow`
- `usb_allowlist`: list of `{ vid, pid, serial? }`
- `temporary_allow_duration_minutes`: integer minutes for temporary allow decisions
- `escalation_threshold`: integer threshold for repeated block escalations

### Device event types (agent -> server)

Supported event types in event schema:
- `device.usb.inserted`
- `device.usb.mass_storage_detected`
- `device.usb.block_applied`
- `device.usb.unblock_requested`
- `device.usb.unblock_approved`
- `device.usb.unblock_applied`

### USB detection payload contract (details_json)

Expected JSON shape in `details_json` for device events:

```json
{
  "device_id": "usb://bus-1-port-2",
  "vid": "abcd",
  "pid": "1234",
  "serial": "SER123",
  "bus": "1-2",
  "vendor_name": "Vendor",
  "product_name": "USB Storage",
  "first_seen_ts": "2026-01-01T00:00:00Z"
}
```

### Policy decision response contract (server contract)

Decision object format for future enforcement wiring:

```json
{
  "action": "BLOCK | ALLOW | TEMP_ALLOW",
  "reason": "string",
  "temporary_allow_minutes": 60,
  "policy_source": "signed|default"
}
```

### Admin APIs (RBAC + audited)

- `POST /api/v1/admin/device/unblock-request`
- `POST /api/v1/admin/device/unblock-approve`

All request/approval actions are audit logged.

## Device Control Enforcement Pilot (OS-Aware)

This phase enables endpoint-side pilot enforcement while preserving safe rollback.

### Modes
- `observe` (safe default): device events are emitted, agent reports `would_block`, no hard block action.
- `enforce`: agent invokes OS adapter block/unblock hooks.

Mode source:
- Policy: `device_enforcement_mode` (`observe|enforce`)
- Agent config fallback: `device_enforcement_mode`

### Command delivery contract
Server uses DB-backed command queue (`agent_commands`) and agent poll/ack APIs:
- `GET /api/v1/agents/{agent_id}/commands`
- `POST /api/v1/agents/{agent_id}/commands/{command_id}/ack`

Admin approvals enqueue commands:
- `DEVICE_UNBLOCK`
- `DEVICE_TEMP_ALLOW` (escalation path)

### Agent config knobs
In `configs/agent.yaml`:
- `device_enforcement_mode`
- `command_poll_interval_sec`
- `failsafe_offline_minutes`

### Safety / Recovery playbook
1. Keep pilot in `observe` during initial rollout.
2. For a blocked endpoint, approve unblock using:
   - `POST /api/v1/admin/device/unblock-approve` (creates `DEVICE_UNBLOCK` command).
3. If server becomes unreachable beyond failsafe window, agent automatically falls back to observe behavior.
4. Temp allow expires automatically unless renewed by new command.

## Offline-Safe Device Control (Local Default Deny + Signed Allow Tokens)

### Offline threat model
Endpoints may be unplugged from server network. In `enforce` mode, mass-storage is blocked locally by default even when server is unreachable.

### Signed allow token workflow
1. Admin issues token: `POST /api/v1/admin/device/allow-token`
2. Token contains claims: `token_id`, `agent_id`, `issued_at`, `expires_at`, `scope`, `reason`, `policy_version`
3. Agent stores token locally and verifies signature offline with configured `token_public_key_path`.
4. If token is valid and scope matches device selector, temporary allow applies until expiry, then auto-reverts to block.

### Local queue and replay
If server is unreachable, device events are queued to local disk and replayed in-order on reconnect.

### Operational recovery guidance
- Keep pilot default in `observe` while validating endpoint compatibility.
- Use time-bound allow tokens for emergency access during outages.
- Revoke a token server-side with `POST /api/v1/admin/device/allow-token/revoke` if risk is detected.
- Verify backlog/health via `/security/status` and audit logs.

## Device Control Enforcement Rollout Safety (OS-Native)

### Rollout strategy
Signed policy supports staged rollout:
- `device_enforcement_rollout.strategy`: `all|percent|allowlist_agents|tags`
- `percent`, `allowlist_agents`, `tags`
- `enforcement_grace_seconds`

### Kill-switch SOP
Emergency endpoint:
- `POST /api/v1/admin/device/kill-switch`

When enabled, server policy decisions force observe/allow behavior and emits `DEVICE_FORCE_OBSERVE` commands for immediate agent-side safety fallback.

### Per-agent controls
- `POST /api/v1/admin/device/set-agent-mode` queues `DEVICE_SET_MODE` and persists override.
- `GET /api/v1/admin/device/rollout/status` returns rollout counters and command backlog.

### OS adapter notes
- Windows adapter uses reversible USBSTOR service-start control (`reg` commands) with local state persistence and reconciliation hooks.
- Linux adapter remains pluggable stub in this phase.

### Recovery playbook
1. Trigger kill-switch for immediate containment of accidental lockout.
2. Confirm rollout status and command backlog in `/api/v1/admin/device/rollout/status`.
3. Use per-agent mode overrides for canary rollback.
4. Restore normal policy and re-apply hashes via queued `DEVICE_APPLY_POLICY_HASH` commands.

## Test Suite Tiers (Release Candidate)

Use the Make targets below from `ecims2/`:

- `make test-current` — **blocking** release gate for current behavior.
- `make test-security` — authoritative security posture subset (mTLS, auth/RBAC, startup encryption, hardening, device enforcement, observability).
- `make test-legacy` — non-blocking historical tests retained for reference.
- `make test` — alias of `make test-current`.

Legacy tests cover historical assumptions (for example, unauthenticated agent registration flows from earlier phases) that are intentionally superseded by current security controls.

## Release Candidate Checklist

### Production environment variables (minimum)
- `ECIMS_ENVIRONMENT=prod`
- `ECIMS_JWT_SECRET` (strong, non-default)
- `ECIMS_BOOTSTRAP_ADMIN_TOKEN`
- `ECIMS_BOOTSTRAP_ADMIN_USERNAME`
- `ECIMS_BOOTSTRAP_ADMIN_PASSWORD`
- `ECIMS_LICENSE_PATH`, `ECIMS_LICENSE_PUBLIC_KEY_PATH`
- `ECIMS_SECURITY_POLICY_PATH`, `ECIMS_SECURITY_POLICY_SIG_PATH`, `ECIMS_SECURITY_POLICY_PUBLIC_KEY_PATH`
- `ECIMS_DEVICE_ALLOW_TOKEN_PRIVATE_KEY_PATH`, `ECIMS_DEVICE_ALLOW_TOKEN_PUBLIC_KEY_PATH`
- `ECIMS_DATA_KEY_PATH` or `ECIMS_DATA_KEY_B64`

### Policy artifacts
- Confirm policy JSON, signature, and public key are present before startup.
- Confirm startup guardrails reject missing/invalid policy artifacts in prod.

### Allow-token key operations
- Keep private signing key offline or restricted to server runtime identity.
- Rotate allow-token key pair on a defined cadence (for example, quarterly) and update deployed public key for agents.
- Revoke outstanding allow-tokens when key compromise is suspected.

### Kill-switch SOP
- Use `POST /api/v1/admin/device/kill-switch` to enable emergency allow mode.
- Record justification + approver in incident ticket and audit logs.
- Disable kill-switch after incident and verify rollout status/backlog clears.

### Rollback steps
1. Enable kill-switch if endpoint blocking must be neutralized immediately.
2. Roll back server package/config to last known good build.
3. Re-run `make test-current` and `make test-security` on rollback candidate.
4. Validate `/health`, `/api/v1/security/status`, and `/api/v1/admin/device/rollout/status`.
5. Disable kill-switch and monitor drift + command backlog.

## Production Packaging & Deployment

### Build packages
```bash
cd ecims2
./scripts/build_server_package.sh
./scripts/build_agent_windows_package.sh
```

Server package output: `dist/ecims_server/`.
Agent package output: `dist/ecims_agent_windows/`.

By default, server package excludes allow-token private keys. To include explicitly:
```bash
ECIMS_INCLUDE_PRIVATE_KEYS=true ./scripts/build_server_package.sh
```

### Templates
- `configs/server.yaml.template`
- `.env.production.template`

### Production startup fail-safe guards
In `prod`, startup refuses to run when:
- JWT secret is weak/default.
- Signed policy artifacts are missing/invalid.
- Data encryption is enabled but key material is missing.
- Allow-token private signing key is missing.

### Optional container deployment
- `Dockerfile`
- `docker-compose.yml` (includes healthcheck)

### Release operations
See `RELEASE.md` for final checklist, backup strategy, kill-switch SOP, offline recovery, and key rotation process.
For end-to-end local run commands and client GUI workflow, see `docs/Phase_16_Client_Runbook.md`.
