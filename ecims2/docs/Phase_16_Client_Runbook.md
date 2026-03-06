# ECIMS Phase 16 Runbook (Hinglish)

## Goal
Ye runbook local-dev se production-hardening tak ka practical flow deta hai, including:
- admin console on `8010` backend
- multi-agent parallel runtime (state isolation)
- dedicated client GUI launch
- final production checklist

## Quick Pre-check
Project root:
```cmd
cd /d X:\ECIMS_2.O-main
```

Python venv + deps already ready na ho to:
```cmd
cd /d X:\ECIMS_2.O-main\ecims2
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r server\requirements.txt
.venv\Scripts\python.exe -m pip install -r agent\requirements.txt
```

Admin dependencies:
```cmd
cd /d X:\ECIMS_2.O-main\ecims_admin
npm install
```

## Step 1: Start Backend (Port 8010)
```cmd
cd /d X:\ECIMS_2.O-main\ecims2
scripts\run_server_local_dev.cmd
```

Health verify:
```cmd
curl.exe http://127.0.0.1:8010/health
```

अगर port conflict aaye (especially stale 8000/8010 process), pehle clear karo:

### CMD
```cmd
for /f "tokens=5" %p in ('netstat -ano ^| findstr LISTENING ^| findstr :8000') do taskkill /F /PID %p
for /f "tokens=5" %p in ('netstat -ano ^| findstr LISTENING ^| findstr :8010') do taskkill /F /PID %p
```

### PowerShell
```powershell
Get-NetTCPConnection -LocalPort 8000,8010 -State Listen -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force }
```

## Step 2: Start Admin Console with Correct API Base URL
### CMD
```cmd
cd /d X:\ECIMS_2.O-main\ecims_admin
set VITE_API_BASE_URL=http://127.0.0.1:8010/api/v1
npm run dev -- --host 127.0.0.1 --port 5173
```

### PowerShell
```powershell
Set-Location X:\ECIMS_2.O-main\ecims_admin
$env:VITE_API_BASE_URL="http://127.0.0.1:8010/api/v1"
npm run dev -- --host 127.0.0.1 --port 5173
```

## Step 3: Start Agents (State-Isolated Parallel Runtime)
Auto-discovery defaults (`configs/agent.local.dev.yaml`) already enabled:
- LAN broadcast (`discovery_udp_port: 40110`)
- mDNS lookup (`_ecims._tcp.local.`) when available

Isliye server URL change ho tab bhi agent discovery attempt karega before fallback.

Single runtime:
```cmd
cd /d X:\ECIMS_2.O-main\ecims2
scripts\run_agent_local_dev.cmd endpoint-local-dev
```

Two isolated runtimes:
```cmd
cd /d X:\ECIMS_2.O-main\ecims2
scripts\run_agent_local_dev.cmd client-a
scripts\run_agent_local_dev.cmd client-b
```

Auto-launch multiple windows:
```cmd
cd /d X:\ECIMS_2.O-main\ecims2
scripts\run_multi_agent_local_dev.cmd client-a client-b client-c
```

PowerShell variants:
```powershell
Set-Location X:\ECIMS_2.O-main\ecims2
.\scripts\run_agent_local_dev.cmd endpoint-local-dev
.\scripts\run_multi_agent_local_dev.cmd client-a client-b client-c
```

Runtime state files yahan aayenge:
```text
ecims2\.ecims_agent_runtime\<runtime-id>\
```

## Step 4: Launch Dedicated Client GUI (Endpoint Operator View)
```cmd
cd /d X:\ECIMS_2.O-main\ecims2
scripts\run_client_gui_local_dev.cmd client-a
```

PowerShell:
```powershell
Set-Location X:\ECIMS_2.O-main\ecims2
.\scripts\run_client_gui_local_dev.cmd client-a
```

GUI features:
- Start/Stop selected runtime agent process
- Runtime local state inspect (`agent_state`, token queue, event queue)
- Direct health check (`/health`)
- Authenticated server sync (`GET /api/v1/agents/{agent_id}/self/status`) using local agent token

## Step 5: E2E Smoke Flow
1) Server + Admin + >=2 agents up karo.
2) Admin login karo and `/agents` page pe online clients check karo.
3) RBAC matrix page (`/admin/roles`) open karke role-permission rows verify karo.
4) Fleet Health page (`/health`) pe `Inspect` click karke Fleet Drill-down card mein:
   - runtime_id
   - state_root
   - command_counts
   - pending command preview
   verify karo.
5) Client GUI (`scripts\run_client_gui_local_dev.cmd client-a`) se `Sync Server Status` click karke same agent ka self-status match karo.

CLI verification:
```cmd
curl.exe http://127.0.0.1:8010/api/v1/agents
```

Admin self-status API direct verify:
```cmd
curl.exe -H "Authorization: Bearer <admin_jwt>" http://127.0.0.1:8010/api/v1/admin/agents/<agent_id>/self-status
```

## Step 6: Validation Commands (Before Handover)
### Backend ops-control plane tests
```cmd
cd /d X:\ECIMS_2.O-main\ecims2
set PYTHONPATH=server
.venv\Scripts\python.exe -m unittest server.tests.test_phase15_ops_control_plane -v
```
```powershell
Set-Location X:\ECIMS_2.O-main\ecims2
$env:PYTHONPATH="server"
.\.venv\Scripts\python.exe -m unittest server.tests.test_phase15_ops_control_plane -v
```

### Agent runtime isolation tests
```cmd
cd /d X:\ECIMS_2.O-main\ecims2
set PYTHONPATH=agent
.venv\Scripts\python.exe -m unittest agent.tests.test_runtime_state_isolation -v
```
```powershell
Set-Location X:\ECIMS_2.O-main\ecims2
$env:PYTHONPATH="agent"
.\.venv\Scripts\python.exe -m unittest agent.tests.test_runtime_state_isolation -v
```

### Admin build
```cmd
cd /d X:\ECIMS_2.O-main\ecims_admin
npm run build
```
```powershell
Set-Location X:\ECIMS_2.O-main\ecims_admin
npm run build
```

## Production-Ready Checklist
## Security baseline
- `ECIMS_ENVIRONMENT=prod`
- `ECIMS_JWT_SECRET` strong + rotated
- `ECIMS_BOOTSTRAP_ADMIN_*` secrets vault se inject karo
- mTLS enforce:
  - `mtls_enabled: true`
  - `mtls_required: true`
- signed policy artifacts mandatory:
  - `security.policy.json`
  - `security.policy.sig`
  - `security.policy.public.pem`

## Crypto and keys
- `ECIMS_DATA_ENCRYPTION_ENABLED=true`
- `ECIMS_DATA_KEY_PATH` ya `ECIMS_DATA_KEY_B64` set
- allow-token private key online exposure minimum rakho
- quarterly key rotation + revoke workflow runbook tested ho

## Ops readiness
- `make test-current`
- `make test-security`
- backup/restore dry-run done:
  - DB snapshot restore
  - state backup preview/apply
- kill-switch SOP rehearsed (`POST /api/v1/admin/device/kill-switch`)

## Client runtime readiness
- each deployed agent ke liye unique `runtime_id`
- shared host pe parallel agents tabhi run karo jab separate runtime IDs configured ho
- runtime dir ke backups aur retention policy defined ho

## Final release gate
- Admin build pass (`npm run build`)
- Phase11-15 tests pass
- agent runtime isolation tests pass
- audit trail for rollout approvals present
- rollback commands documented and validated in staging
