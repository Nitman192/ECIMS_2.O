# ECIMS User Manual

**Product:** Endpoint Configuration Incident Management System (ECIMS) 2.0  
**Document version:** 1.0  
**Baseline release:** `2.0.0-rc1`  
**Primary deployment focus:** Windows EXE package with bundled Admin Console

---

## How to Use This Manual

This manual is written for three operational personas:
- **Administrator** (platform owner and governance controller)
- **SOC Analyst** (incident detection, triage, investigation)
- **Endpoint Operator** (field/client-side runtime operator)

If you are new to ECIMS, start with:
1. [Quick Start in 15 Minutes](#quick-start-in-15-minutes-windows-exe-first)
2. [What ECIMS Solves](#what-ecims-solves-and-where-it-fits)
3. [Windows EXE Setup and First Run](#windows-exe-first-setup-and-first-run)

---

## Quick Start in 15 Minutes (Windows EXE First)

### Dev Flow (fast validation)

1. Build EXE packages:
```powershell
Set-Location X:\ECIMS_2.O-main\ecims2
.\scripts\build_windows_executables.cmd
```

2. Start packaged server:
```powershell
Set-Location X:\ECIMS_2.O-main\ecims2\dist\windows_executables\server
.\start_server.cmd
```

3. Verify backend health:
```powershell
curl.exe http://127.0.0.1:8010/health
```
Expected: JSON with `"status":"ok"`, `"server_version":"2.0.0-rc1"`.

4. Open bundled Admin Console:
- `http://127.0.0.1:8010/`

5. Start client GUI package (same host or another LAN host):
```powershell
Set-Location X:\ECIMS_2.O-main\ecims2\dist\windows_executables\client
.\start_client_gui.cmd client-a
```

### Production Flow (hardened rollout)

1. Prepare signed policy, license, and key artifacts under package `configs/`.
2. Set production env vars (for example `ECIMS_ENVIRONMENT=prod`, strong `ECIMS_JWT_SECRET`, bootstrap admin values).
3. Start server package with validated artifacts and monitor `/health`, `/api/v1/security/status`, and audit logs.
4. Roll out clients in canary waves before full fleet rollout.

---

## What ECIMS Solves and Where It Fits

### Plain-language purpose

ECIMS is a control-plane and endpoint runtime system for:
- Monitoring endpoint configuration and file integrity changes
- Operating controlled remote actions and incident workflows
- Enforcing device-control safety mechanisms with emergency overrides
- Running in offline/LAN-first environments where cloud dependency is undesirable

### Best-fit environments

ECIMS is strongest when you need:
- Air-gapped or tightly controlled LAN operation
- Verifiable governance (audit logs, approvals, two-person style controls)
- Offline-capable endpoint handling (allow-token model, local queue/replay)
- Unified operational surface for security and operational response

### Not a direct fit (without integration)

ECIMS is not designed to replace every enterprise tool category by itself:
- Not a full enterprise SIEM data lake replacement
- Not a full enterprise EDR telemetry/content ecosystem replacement
- Not a CMDB/ITSM ticketing platform replacement

Use ECIMS as a secure, operationally controlled endpoint integrity and response layer, and integrate outward when broader analytics or enterprise workflow needs exist.

---

## ECIMS System Architecture Deep Dive

## 1) ECIMS Server (FastAPI control plane)

The server provides:
- API surface under `/api/v1`
- Authentication and role-based access control
- Audit logging and governance events
- Policy, license, and cryptographic gate enforcement
- Queueing and dispatch logic for endpoint actions
- Bundled Admin Console static hosting on `/`

Operational health endpoint:
- `GET /health`

## 2) ECIMS Agent (endpoint runtime)

The agent provides:
- Endpoint registration/heartbeat/events
- Runtime-isolated local state directory
- Command polling and acknowledgment
- Device control hooks and secure token consumption
- Local queue/replay when server is temporarily unreachable

## 3) ECIMS Admin Console (React UI)

The Admin Console provides:
- Core monitoring pages (dashboard, agents, alerts, audit, security)
- Governance pages (users, roles, feature flags, advanced audit)
- Ops-control pages (remote actions, schedules, enrollment, patching, change control, evidence, playbooks, break glass)

In EXE packaging, the built frontend is bundled inside server package under `admin_frontend/` and served by server root.

## 4) Trust chain: license + policy + keys

ECIMS startup/runtime trust model includes:
- Offline license verification
- Signed security policy verification
- Optional mTLS identity enforcement for agents
- Allow-token signing keypair for controlled device overrides
- Optional data-at-rest encryption key material

Startup guardrails in non-dev and prod are designed to refuse unsafe startup conditions.

---

## Deployment Models and When to Use Them

| Model | Use Case | Why It Works |
| --- | --- | --- |
| **Single-host dev** | Engineer validation and feature testing | Fastest cycle using local scripts and dev settings |
| **Two-PC LAN EXE** | Controlled pilot in lab/network segment | Simple server/client package handoff and isolated runtime IDs |
| **Air-gapped LAN** | Restricted networks with no internet dependency | Offline bundles, signed artifacts, local-first operation |
| **Production hardened** | Enterprise or regulated deployment | Guardrails, strong auth/secrets, signed artifacts, audited workflows |

### Decision guide
- Choose **Windows EXE model first** if your team needs quickest operational onboarding.
- Choose **Python script dev flow** for debugging, development, and test execution.
- Choose **production hardened flow** for any real operational deployment.

---

## Windows EXE-First Setup and First Run

## Prerequisites

- Windows host(s)
- Python venv and Node dependencies available for build host
- ECIMS repository at `X:\ECIMS_2.O-main`

## Build packages

```powershell
Set-Location X:\ECIMS_2.O-main\ecims2
.\scripts\build_windows_executables.cmd
```

Expected outputs:
- `ecims2\dist\windows_executables\server`
- `ecims2\dist\windows_executables\client`
- `ecims2\dist\windows_executables\ecims_server_windows.zip`
- `ecims2\dist\windows_executables\ecims_client_windows.zip`

## Two-machine LAN deployment

### Server machine

```cmd
cd /d <copied_path>\server
start_server.cmd
```

If server advertises wrong NIC/IP:
```cmd
cd /d <copied_path>\server
set ECIMS_DISCOVERY_SERVER_URL=http://<SERVER_LAN_IP>:8010
start_server.cmd
```

### Client machine

GUI mode:
```cmd
cd /d <copied_path>\client
start_client_gui.cmd client-a
```

Headless mode:
```cmd
cd /d <copied_path>\client
start_agent.cmd client-a
```

## First-run validation checklist

1. Health: `curl.exe http://127.0.0.1:8010/health`
2. Admin UI root: `http://<SERVER_IP>:8010/`
3. Agent list: `curl.exe http://127.0.0.1:8010/api/v1/agents`
4. Client runtime folder exists under `.ecims_agent_runtime/<runtime-id>/`

---

## Role-Based Operational Workflows (Day 1 to Day 30)

## Administrator Workflow

### Day 1 (platform bring-up)

1. Validate server health and admin UI availability.
2. Log in and verify:
   - License status page
   - Security status page
   - Roles matrix
3. Create/verify user accounts and role boundaries.
4. Issue enrollment tokens for initial endpoints.

### Day 7 (control stabilization)

1. Validate scheduled maintenance windows and conflicts.
2. Validate remote-action queue lifecycle (sent, ack, done, failed).
3. Run change-control request and state backup preview/apply dry run.
4. Audit-review critical admin actions.

### Day 30 (governance hardening)

1. Review feature flags and rollback posture.
2. Validate break-glass readiness and revoke workflow.
3. Validate patch-update lifecycle with audit evidence.
4. Run retention and export audit report for compliance archive.

## SOC Analyst Workflow

### Day 1

1. Monitor dashboard and alert feed baseline.
2. Use agent inventory to identify endpoint drift and missing heartbeat.
3. Inspect security center for policy/license posture.

### Day 7

1. Triage alerts and correlate with agent self-status.
2. Use playbooks for repeatable response actions with proper approvals.
3. Register and chain evidence records in evidence vault.

### Day 30

1. Trend alert, drift, and command backlog patterns.
2. Validate evidence timeline integrity for selected incidents.
3. Collaborate with admins on policy tuning and safe automation boundaries.

## Endpoint Operator Workflow (Client GUI)

### Day 1

1. Launch client GUI for assigned runtime ID.
2. Use **Quick Setup**.
3. Start monitoring and confirm runtime files are populated.

### Day 7

1. Use Health Check and Sync with Server regularly.
2. Validate local state, token queue, and event queue condition.
3. Practice controlled stop/start of monitoring process.

### Day 30

1. Validate secure-key procedure with admin-approved allow token.
2. Capture and report failures (network, auth, block/unblock state) with exact timestamps.
3. Participate in scheduled rollback drills.

---

## Admin Console Module Guide

This section maps every major UI module to operational intent and primary backend interaction.

## Core Modules

### Dashboard (`/`)

Purpose:
- Fleet posture snapshot and operational trend view.

Key operator actions:
- Review event and policy distribution trends.
- Identify burst conditions quickly.

### Agents (`/agents`)

Purpose:
- Endpoint inventory and operational status.

Key operator actions:
- Verify registration and online status.
- Inspect endpoint records and self-status.
- Run secure declare / one-time key workflows where applicable.

Primary APIs:
- `GET /api/v1/agents`
- `GET /api/v1/admin/agents/{agent_id}/self-status`
- `POST /api/v1/admin/agents/{agent_id}/revoke`
- `POST /api/v1/admin/agents/{agent_id}/restore`

### Alerts (`/alerts`)

Purpose:
- Incident and anomaly detection feed.

Primary API:
- `GET /api/v1/alerts`

### Security Center (`/security`)

Purpose:
- Security hardening and policy/runtime trust posture.

Primary API:
- `GET /api/v1/security/status`

### License Panel (`/license`)

Purpose:
- License validity, capability gates, and expiry posture.

Primary API:
- `GET /api/v1/license/status`

### Audit Logs (`/audit`)

Purpose:
- Control-plane action history and export.

Primary APIs:
- `GET /api/v1/admin/audit`
- `POST /api/v1/admin/audit/export`

## Admin Governance Modules

### Users (`/admin/users`)

Purpose:
- Identity lifecycle and account state control.

Primary APIs:
- `GET /api/v1/admin/users`
- `POST /api/v1/admin/users`
- `PATCH /api/v1/admin/users/{user_id}/role`
- `PATCH /api/v1/admin/users/{user_id}/active`
- `POST /api/v1/admin/users/{user_id}/reset-password`
- `DELETE /api/v1/admin/users/{user_id}`

### Roles Matrix (`/admin/roles`)

Purpose:
- Permission boundary validation by role.

Primary API:
- `GET /api/v1/admin/roles/matrix`

### Feature Flags (`/admin/features`)

Purpose:
- Runtime safety toggles and scoped rollout control.

Primary APIs:
- `GET /api/v1/admin/features`
- `POST /api/v1/admin/features`
- `PUT /api/v1/admin/features/{flag_id}/state`

### Advanced Audit Explorer (`/admin/audit`)

Purpose:
- Deep investigation and export-oriented filtering.

Primary APIs:
- `GET /api/v1/admin/audit`
- `POST /api/v1/admin/audit/export`

## Ops Modules

### Remote Actions (`/ops/remote-actions`)

Purpose:
- Controlled endpoint command dispatch.

Primary APIs:
- `GET /api/v1/admin/ops/remote-actions/tasks`
- `GET /api/v1/admin/ops/remote-actions/tasks/{task_id}/targets`
- `POST /api/v1/admin/ops/remote-actions/tasks`

### Schedules (`/ops/schedules`)

Purpose:
- Planned maintenance orchestration and conflict handling.

Primary APIs:
- `GET /api/v1/admin/ops/schedules`
- `POST /api/v1/admin/ops/schedules`
- `POST /api/v1/admin/ops/schedules/preview`
- `POST /api/v1/admin/ops/schedules/run-due`
- `GET /api/v1/admin/ops/schedules/{schedule_id}/conflicts`
- `POST /api/v1/admin/ops/schedules/{schedule_id}/state`

### Enrollment (`/ops/enrollment`)

Purpose:
- Online and offline onboarding token lifecycle.

Primary APIs:
- `GET /api/v1/admin/ops/enrollment/tokens`
- `POST /api/v1/admin/ops/enrollment/tokens`
- `POST /api/v1/admin/ops/enrollment/tokens/{token_id}/revoke`
- `POST /api/v1/admin/ops/enrollment/offline-kit/import`

### Fleet Health (`/ops/health`)

Purpose:
- Endpoint posture + drill-down runtime status.

Primary APIs:
- `GET /api/v1/admin/metrics`
- `GET /api/v1/admin/device/fleet/drift`
- `GET /api/v1/admin/agents/{agent_id}/self-status`

### Quarantine (`/ops/quarantine`)

Purpose:
- Reversible endpoint isolation workflow.

Common dependent API surface:
- Remote action task APIs under `/admin/ops/remote-actions/...`

### Evidence Vault (`/ops/evidence-vault`)

Purpose:
- Tamper-evident evidence objects with custody timeline and export.

Primary APIs:
- `GET /api/v1/admin/ops/evidence-vault`
- `POST /api/v1/admin/ops/evidence-vault`
- `GET /api/v1/admin/ops/evidence-vault/{evidence_id}`
- `GET /api/v1/admin/ops/evidence-vault/{evidence_id}/timeline`
- `POST /api/v1/admin/ops/evidence-vault/{evidence_id}/custody`
- `POST /api/v1/admin/ops/evidence-vault/{evidence_id}/export`

### Playbooks (`/ops/playbooks`)

Purpose:
- Repeatable response templates with approval models.

Primary APIs:
- `GET /api/v1/admin/ops/playbooks`
- `POST /api/v1/admin/ops/playbooks`
- `GET /api/v1/admin/ops/playbooks/runs`
- `POST /api/v1/admin/ops/playbooks/{playbook_id}/execute`
- `POST /api/v1/admin/ops/playbooks/runs/{run_id}/decision`

### Change Control (`/ops/change-control`)

Purpose:
- Controlled governance for high-impact changes with backup support.

Primary APIs:
- `GET /api/v1/admin/ops/change-control/requests`
- `POST /api/v1/admin/ops/change-control/requests`
- `POST /api/v1/admin/ops/change-control/requests/{request_id}/decision`
- `GET /api/v1/admin/ops/state-backups`
- `POST /api/v1/admin/ops/state-backups`
- `GET /api/v1/admin/ops/state-backups/{backup_id}`
- `POST /api/v1/admin/ops/state-backups/{backup_id}/restore/preview`
- `POST /api/v1/admin/ops/state-backups/{backup_id}/restore/apply`

### Patch Updates (`/ops/patch-updates`)

Purpose:
- Offline package vault and auditable rollout control.

Primary APIs:
- `GET /api/v1/admin/ops/patch-updates`
- `POST /api/v1/admin/ops/patch-updates/upload`
- `GET /api/v1/admin/ops/patch-updates/{patch_id}/download`
- `POST /api/v1/admin/ops/patch-updates/{patch_id}/apply`

### Break Glass (`/ops/break-glass`)

Purpose:
- Emergency privileged workflow with strict lifecycle.

Primary APIs:
- `GET /api/v1/admin/ops/break-glass/sessions`
- `POST /api/v1/admin/ops/break-glass/sessions`
- `POST /api/v1/admin/ops/break-glass/sessions/{session_id}/revoke`

---

## Client GUI Practical Guide

Client GUI entry points:
- Dev script: `scripts\run_client_gui_local_dev.cmd <runtime-id>`
- Packaged EXE: `start_client_gui.cmd <runtime-id>`

## 1) Quick Setup button

What it does:
- Refreshes local runtime snapshot
- Calls health endpoint
- Attempts server status sync for local agent identity

Use when:
- First launch
- After server restart
- After network changes

## 2) Start / Stop Monitoring

- **Start Monitoring** launches agent process for selected runtime.
- **Stop Monitoring** performs graceful terminate with forced kill fallback.

Expected process status examples:
- `running (pid=...)`
- `stopped`
- `stopped (exit=<code>)`

## 3) Health Check and Sync with Server

- Health Check requests `<server_url>/health`.
- Sync with Server requests:
  - `GET /api/v1/agents/{agent_id}/self/status` using local agent token.

If sync fails, check:
- agent enrolled state
- local token presence
- server reachability and token validity

## 4) Runtime file interpretation

Typical runtime files under `.ecims_agent_runtime/<runtime-id>/`:

| File | Meaning |
| --- | --- |
| `agent_state.json` | Agent identity/runtime state (token masked in GUI view) |
| `agent_tokens.json` | Token-related local data |
| `agent_event_queue.json` | Deferred outbound events while offline/unreachable |
| `device_adapter_state.json` | Device adapter state snapshot |
| `runtime.lock` | Active runtime lock coordination file |

## 5) Secure key flow (manual allow-token usage)

Expected successful flow:
1. Operator pastes secure key (allow token).
2. GUI validates and consumes token locally.
3. Adapter applies unblock action.
4. Best-effort sync attempts:
   - consume token on server
   - post unblock event
5. GUI confirms secure-key acceptance and refreshes state.

Common failure conditions:
- Token invalid/expired/scope mismatch
- Agent not enrolled yet
- Missing admin privilege for local OS unblock operation
- Temporary server unreachability (local apply may still succeed)

---

## Security Model Explained Simply

## JWT auth + RBAC

- Login issues JWT (`POST /api/v1/auth/login`).
- Session/user introspection uses `GET /api/v1/auth/me`.
- Password reset self-flow uses `POST /api/v1/auth/password/reset`.
- Role boundaries include `ADMIN`, `ANALYST`, `VIEWER`.

## Signed security policy

- Server loads policy + signature + policy public key at startup.
- In hardened modes, invalid/missing signed policy blocks safe startup.

## mTLS and endpoint identity checks

- Agent-to-server can enforce mutual TLS.
- Identity mismatch or revoked endpoint identity is blocked and audited.

## Offline license gating

- Startup validates offline signed license.
- License controls availability of selected features (for example AI endpoints).

## Allow-token and kill-switch safety model

- Allow tokens: bounded, signed, offline-verifiable temporary exceptions.
- Kill switch: emergency fallback mechanism to reduce lockout risk.
- Per-agent mode controls support staged recovery and controlled rollback.

Device-control admin APIs:
- `POST /api/v1/admin/device/unblock-request`
- `POST /api/v1/admin/device/unblock-approve`
- `POST /api/v1/admin/device/allow-token`
- `POST /api/v1/admin/device/allow-token/revoke`
- `POST /api/v1/admin/device/secure-declare`
- `POST /api/v1/admin/device/kill-switch`
- `POST /api/v1/admin/device/set-agent-mode`
- `GET /api/v1/admin/device/rollout/status`

---

## End-to-End Scenario Examples

## Scenario 1: New endpoint onboarding

Goal:
- Register and validate a new endpoint agent with traceable enrollment controls.

Steps:
1. Admin issues enrollment token from Enrollment module.
2. Endpoint operator starts client runtime with runtime ID.
3. Agent enrolls/registers and begins heartbeat/events.
4. Admin verifies endpoint in Agents page.

Primary APIs involved:
- `POST /api/v1/admin/ops/enrollment/tokens`
- `POST /api/v1/agents/enroll`
- `POST /api/v1/agents/register`
- `POST /api/v1/agents/heartbeat`

Success checkpoints:
- Agent appears in `/agents`.
- Heartbeat freshness is healthy.
- Audit records contain enrollment and registration actions.

## Scenario 2: Incident triage from alert to evidence export

Goal:
- Move from detection to forensics-ready evidence artifact.

Steps:
1. Analyst reviews Alerts page and identifies suspicious endpoint.
2. Analyst/Admin inspects agent self-status and pending commands.
3. Evidence object is created and custody events are appended.
4. Evidence bundle is exported for formal incident package.

Primary APIs involved:
- `GET /api/v1/alerts`
- `GET /api/v1/admin/agents/{agent_id}/self-status`
- `POST /api/v1/admin/ops/evidence-vault`
- `POST /api/v1/admin/ops/evidence-vault/{evidence_id}/custody`
- `POST /api/v1/admin/ops/evidence-vault/{evidence_id}/export`

Success checkpoints:
- Evidence has complete timeline entries.
- Export artifact generated and archived.
- Audit trail includes actor, action, and target references.

## Scenario 3: Controlled patch rollout with backup and apply audit

Goal:
- Deploy offline patch package with controlled rollback path.

Steps:
1. Admin creates state backup snapshot.
2. Admin uploads patch package into patch vault.
3. Target host downloads and applies patch locally.
4. Admin marks apply workflow and records result.
5. If needed, restore preview/apply from backup.

Primary APIs involved:
- `POST /api/v1/admin/ops/state-backups`
- `POST /api/v1/admin/ops/patch-updates/upload`
- `GET /api/v1/admin/ops/patch-updates/{patch_id}/download`
- `POST /api/v1/admin/ops/patch-updates/{patch_id}/apply`
- `POST /api/v1/admin/ops/state-backups/{backup_id}/restore/preview`
- `POST /api/v1/admin/ops/state-backups/{backup_id}/restore/apply`

Success checkpoints:
- Backup ID mapped to rollout ticket.
- Patch status transitions are visible and audited.
- Restore preview is available before destructive rollback.

## Scenario 4: Emergency break-glass session

Goal:
- Grant and then revoke emergency access under strict control.

Steps:
1. Admin creates break-glass session with reason/expiry.
2. Emergency task executed under approved session.
3. Session revoked when emergency ends.
4. Audit export attached to post-incident report.

Primary APIs involved:
- `POST /api/v1/admin/ops/break-glass/sessions`
- `GET /api/v1/admin/ops/break-glass/sessions`
- `POST /api/v1/admin/ops/break-glass/sessions/{session_id}/revoke`
- `POST /api/v1/admin/audit/export`

Success checkpoints:
- Time-bound session lifecycle visible.
- Revocation completed and logged.
- No stale emergency session left active.

## Scenario 5: Offline USB unblock via secure key

Goal:
- Allow temporary endpoint access during outage without bypassing control design.

Steps:
1. Admin issues signed allow token.
2. Endpoint operator enters secure key in Client GUI.
3. Agent validates token locally and attempts unblock.
4. On reconnect, event and token-consume status sync to server.

Primary APIs involved:
- `POST /api/v1/admin/device/allow-token`
- `POST /api/v1/agents/{agent_id}/device/allow-token/consume`
- `POST /api/v1/agents/events`

Success checkpoints:
- Local unblock performed only when token validates.
- Token is time-bounded and single-use semantics enforced.
- Event timeline captures secure-key action.

---

## Troubleshooting and Recovery Playbooks

## 1) Port conflicts (8010)

Symptom:
- Server fails to bind or health endpoint not reachable.

Resolution (PowerShell):
```powershell
Get-NetTCPConnection -LocalPort 8000,8010 -State Listen -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force }
```

Then restart server and re-check:
```powershell
curl.exe http://127.0.0.1:8010/health
```

## 2) Agent not appearing in inventory

Check list:
1. Verify server reachable from endpoint.
2. Verify runtime ID and config path in client startup command.
3. Check local runtime files under `.ecims_agent_runtime/<runtime-id>/`.
4. Validate enrollment token and registration flow.
5. Validate discovery advertisement URL for multi-NIC hosts.

Useful APIs:
- `GET /api/v1/agents`
- `GET /api/v1/admin/agents/{agent_id}/self-status`

## 3) Authentication or session failures

Check list:
1. Confirm correct login endpoint usage (`POST /api/v1/auth/login`).
2. Confirm JWT expiry and session timeout behavior.
3. Validate user active state and role assignment.
4. Reset password if required by policy.

Relevant APIs:
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/password/reset`

## 4) Patch upload/download/apply issues

Check list:
1. Confirm file size within `patch_update_max_file_bytes` limit.
2. Confirm patch exists before download/apply attempt.
3. Confirm network and permissions on target machine.
4. Confirm state backup exists before high-risk apply operation.

Relevant APIs:
- `GET /api/v1/admin/ops/patch-updates`
- `POST /api/v1/admin/ops/patch-updates/upload`
- `GET /api/v1/admin/ops/patch-updates/{patch_id}/download`
- `POST /api/v1/admin/ops/patch-updates/{patch_id}/apply`

## 5) Kill-switch rollback and recovery checks

Recovery pattern:
1. Enable kill-switch to reduce lockout blast radius.
2. Verify rollout status and command backlog.
3. Apply per-agent mode overrides if needed.
4. Roll back package/config and validate baseline health/security endpoints.
5. Disable kill-switch after stability confirmation.

Critical APIs:
- `POST /api/v1/admin/device/kill-switch`
- `GET /api/v1/admin/device/rollout/status`
- `POST /api/v1/admin/device/set-agent-mode`
- `GET /health`
- `GET /api/v1/security/status`

---

## ECIMS vs Others (Practical Comparison)

This section is intentionally ECIMS-focused for offline/LAN-controlled environments while still listing valid non-fit cases.

### Side-by-side capability view

| Dimension | ECIMS | Wazuh | Microsoft Defender for Endpoint | Tripwire Enterprise |
| --- | --- | --- | --- | --- |
| Air-gapped and LAN-first operation | **Strong**. Designed for offline/LAN packages and local trust artifacts | Moderate. Can run on-prem, but broader stack design often assumes SIEM integrations | Limited for fully disconnected operation in many deployments | Strong for on-prem FIM use cases |
| Endpoint config integrity depth | **Strong**. Integrity + response workflows in one control plane | Strong FIM and detection coverage | Broad EDR/XDR depth, integrity is one part of larger scope | **Strong** in file/config integrity and compliance monitoring |
| Device control with emergency override | **Strong**. Allow-token + kill-switch + mode override model | Usually integration-driven or custom policy extensions | Strong device-control ecosystem, but model is vendor-policy centric | More integrity/compliance centric than emergency device override orchestration |
| Governance controls (change control, approvals, evidence chain) | **Strong** built-in ops governance surfaces | Moderate, often requires process/tooling around core platform | Strong enterprise governance if combined with Microsoft security stack | Strong compliance orientation; workflow depth depends on surrounding tooling |
| Deployment complexity | Moderate and predictable for ECIMS package model | Moderate to high depending on architecture | High if tenant-wide enterprise integration is required | Moderate to high in large regulated estates |
| Ecosystem breadth and integrations | Focused scope, smaller ecosystem | Broad open-source ecosystem | Very broad enterprise ecosystem | Mature compliance ecosystem |
| Non-fit case | Not a full SIEM/EDR replacement by itself | May require additional governance tooling to match ECIMS workflow style | May be heavy for offline-first isolated environments | May need companion systems for richer response orchestration |

### Practical decision examples

## Example A: Isolated defense manufacturing LAN

Choose **ECIMS** when:
- Internet dependency is disallowed
- Signed offline artifacts and local control are mandatory
- You need integrated patch/change/evidence workflows in one plane

Choose alternative when:
- You need full enterprise XDR with global threat intel correlation across cloud services (consider Defender stack).

## Example B: SOC-heavy enterprise with mature cloud stack

Choose **alternative-first** when:
- Existing Microsoft-centric detection and response stack is deeply integrated
- You need large ecosystem automation and tenant-scale analytics immediately

Choose **ECIMS** as complementary layer when:
- You still require strict offline-capable endpoint control workflows for selected network zones.

## Example C: Compliance-first file integrity program

Choose **ECIMS** when:
- You want integrity + incident action + governance flows in one interface
- You need operational controls (playbooks, change control, break glass) tightly coupled to endpoint state

Choose **Tripwire-first** when:
- Primary requirement is deep FIM/compliance reporting with existing compliance process alignment and less emphasis on integrated control-plane operations.

---

## Strengths, Limitations, and Best-Fit Guidance

## Key strengths

- Offline/LAN-first operational design
- Bundled Windows EXE deployment path with integrated admin frontend
- Unified operational modules: enrollment, scheduling, patch updates, playbooks, evidence, change control
- Strong safety primitives for device-control rollout and rollback
- Role-based governance and auditable operations by design

## Important limitations

- Not intended to replace full SIEM data lake or full enterprise EDR ecosystem on its own
- Integration ecosystem is narrower than hyperscale security platforms
- Linux USB enforcement path is less feature-complete than Windows-focused flow
- Requires disciplined key/policy/license operations to realize full security posture

## Best-fit profile

ECIMS is best when your organization prioritizes:
- Controlled on-prem or air-gapped operation
- Endpoint integrity and operational governance in one product surface
- Deterministic, auditable workflows over broad cloud-native telemetry breadth

---

## FAQ

### 1) Is ECIMS a SIEM replacement?
No. ECIMS is a control-plane and endpoint integrity/response platform. It can complement SIEM tooling.

### 2) Can ECIMS run without internet?
Yes. ECIMS is designed for offline/LAN operation with signed artifacts and local runtime controls.

### 3) Is mTLS mandatory?
In hardened policies and production, mTLS should be enforced. Dev mode allows relaxed settings for local testing.

### 4) Can I deploy quickly without running a separate admin frontend server?
Yes. The Windows server EXE package serves the bundled Admin Console at `http://<server-ip>:8010/`.

### 5) How do I avoid endpoint lockout during enforcement rollout?
Use staged rollout, keep kill-switch SOP ready, and validate per-agent mode overrides before full enforcement.

### 6) What is the minimum first validation after deployment?
Run `/health`, open Admin UI root, confirm at least one agent heartbeat, and verify audit log ingestion.

---

## Glossary

- **Agent:** Endpoint-side runtime that registers, sends telemetry, and executes approved commands.
- **Admin Console:** Web UI for monitoring, governance, and operational workflows.
- **Allow Token:** Signed, time-bounded artifact allowing temporary device unblock behavior.
- **Break Glass:** Controlled emergency access session with strict auditability and expiry.
- **Drift:** Deviation between expected policy/baseline and observed endpoint state.
- **Kill Switch:** Emergency mechanism to reduce endpoint enforcement blast radius.
- **Playbook:** Predefined operational response template with optional approval gates.
- **State Backup:** Point-in-time server state bundle for controlled restore workflows.
- **Runtime ID:** Unique identifier to isolate local agent runtime state.

---

## Command Appendix

## Dev Flow Commands

### Start local dev server
```cmd
cd /d X:\ECIMS_2.O-main\ecims2
scripts\run_server_local_dev.cmd
```

### Start local admin frontend (separate dev server)
```cmd
cd /d X:\ECIMS_2.O-main\ecims_admin
set VITE_API_BASE_URL=http://127.0.0.1:8010/api/v1
npm run dev -- --host 127.0.0.1 --port 5173
```

### Start local agent runtime
```cmd
cd /d X:\ECIMS_2.O-main\ecims2
scripts\run_agent_local_dev.cmd client-a
```

### Start local client GUI
```cmd
cd /d X:\ECIMS_2.O-main\ecims2
scripts\run_client_gui_local_dev.cmd client-a
```

### Validation tests
```cmd
cd /d X:\ECIMS_2.O-main\ecims2
set PYTHONPATH=server
.venv\Scripts\python.exe -m unittest server.tests.test_phase15_ops_control_plane -v
```

```cmd
cd /d X:\ECIMS_2.O-main\ecims2
set PYTHONPATH=agent
.venv\Scripts\python.exe -m unittest agent.tests.test_runtime_state_isolation -v
```

### Build admin frontend
```cmd
cd /d X:\ECIMS_2.O-main\ecims_admin
npm run build
```

## Production Flow Commands

### Build Windows EXE bundles
```cmd
cd /d X:\ECIMS_2.O-main\ecims2
scripts\build_windows_executables.cmd
```

### Start packaged server
```cmd
cd /d <copied_path>\server
start_server.cmd
```

### Start packaged client GUI
```cmd
cd /d <copied_path>\client
start_client_gui.cmd client-a
```

### Start packaged headless agent
```cmd
cd /d <copied_path>\client
start_agent.cmd client-a
```

---

## API Endpoint Index

The following index maps major operational endpoints.

## Authentication

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/password/reset`

## Agent lifecycle and telemetry

- `POST /api/v1/agents/register`
- `POST /api/v1/agents/enroll`
- `POST /api/v1/agents/heartbeat`
- `POST /api/v1/agents/events`
- `GET /api/v1/agents/{agent_id}/commands`
- `POST /api/v1/agents/{agent_id}/commands/{command_id}/ack`
- `POST /api/v1/agents/{agent_id}/device/status`
- `POST /api/v1/agents/{agent_id}/device/allow-token/consume`
- `GET /api/v1/agents/{agent_id}/self/status`
- `GET /api/v1/agents`
- `GET /api/v1/alerts`

## Platform status

- `GET /health`
- `GET /api/v1/license/status`
- `GET /api/v1/security/status`
- `GET /api/v1/admin/metrics`
- `GET /api/v1/admin/device/fleet/drift`

## Agent admin actions

- `POST /api/v1/admin/agents/{agent_id}/revoke`
- `POST /api/v1/admin/agents/{agent_id}/restore`
- `GET /api/v1/admin/agents/{agent_id}/self-status`

## Baseline and retention

- `POST /api/v1/admin/run_offline_check`
- `POST /api/v1/admin/baseline/approve`
- `POST /api/v1/admin/retention/run`

## Identity and governance

- `GET /api/v1/admin/roles/matrix`
- `GET /api/v1/admin/users`
- `POST /api/v1/admin/users`
- `PATCH /api/v1/admin/users/{user_id}/role`
- `PATCH /api/v1/admin/users/{user_id}/active`
- `POST /api/v1/admin/users/{user_id}/reset-password`
- `DELETE /api/v1/admin/users/{user_id}`
- `GET /api/v1/admin/features`
- `POST /api/v1/admin/features`
- `PUT /api/v1/admin/features/{flag_id}/state`
- `GET /api/v1/admin/audit`
- `POST /api/v1/admin/audit/export`

## Ops control plane

- `GET /api/v1/admin/ops/remote-actions/tasks`
- `GET /api/v1/admin/ops/remote-actions/tasks/{task_id}/targets`
- `POST /api/v1/admin/ops/remote-actions/tasks`
- `GET /api/v1/admin/ops/schedules`
- `POST /api/v1/admin/ops/schedules`
- `POST /api/v1/admin/ops/schedules/preview`
- `POST /api/v1/admin/ops/schedules/run-due`
- `GET /api/v1/admin/ops/schedules/{schedule_id}/conflicts`
- `POST /api/v1/admin/ops/schedules/{schedule_id}/state`
- `GET /api/v1/admin/ops/enrollment/tokens`
- `POST /api/v1/admin/ops/enrollment/tokens`
- `POST /api/v1/admin/ops/enrollment/tokens/{token_id}/revoke`
- `POST /api/v1/admin/ops/enrollment/offline-kit/import`
- `GET /api/v1/admin/ops/evidence-vault`
- `POST /api/v1/admin/ops/evidence-vault`
- `GET /api/v1/admin/ops/evidence-vault/{evidence_id}`
- `GET /api/v1/admin/ops/evidence-vault/{evidence_id}/timeline`
- `POST /api/v1/admin/ops/evidence-vault/{evidence_id}/custody`
- `POST /api/v1/admin/ops/evidence-vault/{evidence_id}/export`
- `GET /api/v1/admin/ops/playbooks`
- `POST /api/v1/admin/ops/playbooks`
- `GET /api/v1/admin/ops/playbooks/runs`
- `POST /api/v1/admin/ops/playbooks/{playbook_id}/execute`
- `POST /api/v1/admin/ops/playbooks/runs/{run_id}/decision`
- `GET /api/v1/admin/ops/change-control/requests`
- `POST /api/v1/admin/ops/change-control/requests`
- `POST /api/v1/admin/ops/change-control/requests/{request_id}/decision`
- `GET /api/v1/admin/ops/state-backups`
- `POST /api/v1/admin/ops/state-backups`
- `GET /api/v1/admin/ops/state-backups/{backup_id}`
- `POST /api/v1/admin/ops/state-backups/{backup_id}/restore/preview`
- `POST /api/v1/admin/ops/state-backups/{backup_id}/restore/apply`
- `GET /api/v1/admin/ops/patch-updates`
- `POST /api/v1/admin/ops/patch-updates/upload`
- `GET /api/v1/admin/ops/patch-updates/{patch_id}/download`
- `POST /api/v1/admin/ops/patch-updates/{patch_id}/apply`
- `GET /api/v1/admin/ops/break-glass/sessions`
- `POST /api/v1/admin/ops/break-glass/sessions`
- `POST /api/v1/admin/ops/break-glass/sessions/{session_id}/revoke`

## Device-control and emergency APIs

- `POST /api/v1/admin/device/unblock-request`
- `POST /api/v1/admin/device/unblock-approve`
- `POST /api/v1/admin/device/allow-token`
- `POST /api/v1/admin/device/secure-declare`
- `POST /api/v1/admin/device/allow-token/revoke`
- `POST /api/v1/admin/device/kill-switch`
- `POST /api/v1/admin/device/set-agent-mode`
- `GET /api/v1/admin/device/rollout/status`

## AI operations

- `POST /api/v1/ai/train`
- `POST /api/v1/ai/score/run`
- `GET /api/v1/ai/scores`
- `GET /api/v1/ai/models`

---

## Final Operational Notes

- Keep runtime IDs unique per endpoint runtime.
- Keep allow-token private keys and encryption keys protected under strict access control.
- Treat this manual as living operational documentation; update it when new modules, routes, or rollout procedures are introduced.
