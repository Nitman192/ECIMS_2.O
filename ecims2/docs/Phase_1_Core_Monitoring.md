# ECIMS 2.0 Phase 1 Core Monitoring

Phase 1 establishes secure agent-server communication for offline/LAN environments.

## Implemented Features
- Agent registration and token issuance.
- Periodic heartbeats and computed online/offline status.
- File inventory scanning using SHA-256.
- Baseline comparison on server for new, modified, and deleted files.
- Alert creation with Phase 1 severity mapping.
- Manual offline alert trigger endpoint.

## Security addendum (ported from PR4)
- **At-rest encryption utilities** are now available under `server/app/security/storage_crypto.py`.
- **Data keyring lifecycle** scripts are available:
  - `scripts/generate_data_key.py`
  - `scripts/rotate_data_key.py`
- **TLS/mTLS support modules** are available under `server/app/security/tls.py` and `server/app/security/mtls.py`.
- **mTLS bootstrap script** is available at `scripts/generate_mtls_ca.py`.

### Production posture
- Plaintext fallback for encrypted storage is **disallowed in production** (`ECIMS_ENVIRONMENT=prod`).
- Encryption keys must come from environment/secrets via `ECIMS_KEYRING_PATH`-managed keyring artifacts.

## Alert Mapping
- `NEW_FILE` -> `AMBER`
- `FILE_MODIFIED` -> `RED`
- `FILE_DELETED` -> `RED`
- `AGENT_OFFLINE` -> `AMBER`

## Next Phase Candidates
- Windows service packaging for agent.
- Real rate limiter.
- Dashboard and analytics.
