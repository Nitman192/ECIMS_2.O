# ECIMS 2.0 Phase 1 Core Monitoring

Phase 1 establishes secure agent-server communication for offline/LAN environments.

## Implemented Features
- Agent registration and token issuance.
- Periodic heartbeats and computed online/offline status.
- File inventory scanning using SHA-256.
- Baseline comparison on server for new, modified, and deleted files.
- Alert creation with Phase 1 severity mapping.
- Manual offline alert trigger endpoint.

## Alert Mapping
- `NEW_FILE` -> `AMBER`
- `FILE_MODIFIED` -> `RED`
- `FILE_DELETED` -> `RED`
- `AGENT_OFFLINE` -> `AMBER`

## Next Phase Candidates
- Windows service packaging for agent.
- Auth hardening and replay protection.
- Real rate limiter.
- Dashboard and analytics.
