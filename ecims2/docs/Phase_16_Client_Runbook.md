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

Runtime state files yahan aayenge:
```text
ecims2\.ecims_agent_runtime\<runtime-id>\
```

## Step 4: Launch Dedicated Client GUI (Endpoint Operator View)
```cmd
cd /d X:\ECIMS_2.O-main\ecims2
scripts\run_client_gui_local_dev.cmd client-a
```

GUI features:
- Start/Stop selected runtime agent process
- Runtime local state inspect (`agent_state`, token queue, event queue)
- Direct health check (`/health`)

## Step 5: E2E Smoke Flow
1) Server + Admin + >=2 agents up karo.
2) Admin login karo and `/agents` page pe online clients check karo.
3) RBAC matrix page (`/admin/roles`) open karke role-permission rows verify karo.
4) Device health/ops pages pe agent heartbeat + status reconcile verify karo.

CLI verification:
```cmd
curl.exe http://127.0.0.1:8010/api/v1/agents
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
- audit trail for rollout approvals present
- rollback commands documented and validated in staging
