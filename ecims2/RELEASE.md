# ECIMS 2.0 Release Checklist

## Target Versions
- Server: `v2.0.0-rc1` -> `v2.0.0`
- Agent: `v2.0.0-rc1` -> `v2.0.0`

## Required Environment Variables (Production)
- `ECIMS_ENVIRONMENT=prod`
- `ECIMS_JWT_SECRET`
- `ECIMS_BOOTSTRAP_ADMIN_TOKEN`
- `ECIMS_BOOTSTRAP_ADMIN_USERNAME`
- `ECIMS_BOOTSTRAP_ADMIN_PASSWORD`
- `ECIMS_LICENSE_PATH`, `ECIMS_LICENSE_PUBLIC_KEY_PATH`
- `ECIMS_SECURITY_POLICY_PATH`, `ECIMS_SECURITY_POLICY_SIG_PATH`, `ECIMS_SECURITY_POLICY_PUBLIC_KEY_PATH`
- `ECIMS_DEVICE_ALLOW_TOKEN_PUBLIC_KEY_PATH`, `ECIMS_DEVICE_ALLOW_TOKEN_PRIVATE_KEY_PATH`
- `ECIMS_DATA_ENCRYPTION_ENABLED=true` and (`ECIMS_DATA_KEY_PATH` or `ECIMS_DATA_KEY_B64`)

## Rollout Plan
1. Build artifacts: `scripts/build_server_package.sh` and `scripts/build_agent_windows_package.sh`.
2. Deploy server package to staging with signed policy artifacts.
3. Run `make test-current` and `make test-security` pre-prod.
4. Canary rollout to subset of agents using per-agent overrides.
5. Expand rollout after drift/metrics stable.

## Emergency Kill-Switch Procedure
1. Call `POST /api/v1/admin/device/kill-switch` with reason.
2. Verify `/api/v1/admin/device/rollout/status` shows `enabled=true`.
3. Audit incident ID + approver in ticket system.
4. Disable switch after remediation and validate command backlog drains.

## Offline Recovery Process
- Agent default deny remains active when server unreachable in enforce mode unless explicit observe fallback policy/kill-switch.
- If agent token store is missing/corrupt, endpoint reverts to blocked behavior.
- Restore policy artifacts from signed backup and restart server.

## Backup Strategy
### Database backup
- Stop writes or enter maintenance window.
- File-level copy of SQLite DB (`cp ecims2.db ecims2.db.bak-<timestamp>`).
- Periodically test restore by starting service with copied DB path.

### Key backup
- Backup allow-token private key and data encryption keyring in offline encrypted vault.
- Enforce dual control for key restore operations.

### Policy artifact verification
- Verify policy signature against policy public key before deployment.
- Confirm server startup logs indicate `Policy ... reason=OK`.

## Key Rotation Process
1. Generate new allow-token key pair.
2. Deploy new public key to agents and server policy.
3. Switch server signing key path to new private key.
4. Revoke outstanding tokens as required.
5. Audit rotation event and update runbook.
