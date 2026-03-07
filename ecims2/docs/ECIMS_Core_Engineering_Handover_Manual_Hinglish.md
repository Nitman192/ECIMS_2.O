# ECIMS Core Engineering Handover Manual (Hinglish)

**Project:** ECIMS 2.0 (Endpoint Configuration Incident Management System)  
**Document Type:** Producer/Developer/Core Handover Manual  
**Primary Focus:** "Repo me kya kahan hai, kyun hai, kaise change karna hai, patch ka end-to-end lifecycle kya hai"

---

## 1. Is Manual Ka Objective

Yeh manual un logon ke liye hai jo ECIMS ko:
- Deep level par samajhna chahte hain
- Project handover lena/dena chahte hain
- Future feature changes ya production patches safely implement karna chahte hain

Simple language me: **"Kaunsa feature kis file family me rehta hai, change karne ka sahi entry-point kya hai, aur rollout/rollback ka process kya hai"**.

---

## 2. Recommended Reading Order

1. `ecims2/docs/ECIMS_User_Manual.md` (operator/admin level)
2. `ecims2/docs/Phase_16_Client_Runbook.md` (run and verification flow)
3. `ecims2/README.md` (phase and feature baseline)
4. Current manual (yeh file) for core engineering ownership and modification strategy

---

## 3. High-Level System Architecture (Bird's Eye View)

ECIMS major components:

1. **Server Control Plane** (`ecims2/server/app/...`)
2. **Endpoint Agent Runtime** (`ecims2/agent/ecims_agent/...`)
3. **Admin Console (React)** (`ecims_admin/src/...`)
4. **Packaging + Ops Scripts** (`ecims2/scripts/...`)
5. **License Authority Tooling (offline trust)** (`license_authority/`, `license_authority_gui/`)

Data flow summary:

1. Agent register/enroll karta hai -> token leta hai -> heartbeat/events bhejta hai.
2. Server events process karta hai -> alerts/create/update + audit log.
3. Admin Console APIs call karta hai -> server services business logic execute karti hain.
4. Ops actions (remote actions, schedules, playbooks, patch workflow, backup/restore) DB + audit me persist hote hain.
5. Patch packages server vault me store hote hain; deployment mostly offline/manual controlled process hai.

---

## 4. Repository Ownership Map (Top Level)

| Path | Responsibility | Kab yahan change karna hai |
| --- | --- | --- |
| `ecims2/server` | Backend API, business logic, DB schema, security gates | New backend feature, endpoint contract change, policy/auth logic change |
| `ecims2/agent` | Endpoint behavior, scanning, device control, token consume, local runtime state | Endpoint-side functionality, command handling, USB/block behavior |
| `ecims_admin` | Web admin UX and API bindings | Dashboard/page workflows, forms, UI validations, API consumption |
| `ecims2/scripts` | Build/package/run/migration/dev tooling | Packaging process, local run automation, release operations |
| `ecims2/configs` | Runtime config and security policy artifacts | Default behavior tuning, deployment templates, policy knobs |
| `license_authority` | Offline license and mTLS artifact generation | License pipeline changes, key generation workflows |
| `license_authority_gui` | Offline authority operator GUI (secure artifact ops) | GUI-based key/license workflow changes |

---

## 5. Backend Core File Responsibility (Server)

### 5.1 Boot, config, middleware, static hosting

| File | Role | Change trigger |
| --- | --- | --- |
| `ecims2/server/app/main.py` | App startup, middleware, startup guardrails, admin static bundle hosting | Startup behavior, middlewares, health payload, static serving behavior |
| `ecims2/server/app/core/config.py` | All typed settings + env override mapping | New env var, config field, runtime knob |
| `ecims2/server/app/core/version.py` | `SERVER_VERSION`, `SCHEMA_VERSION` | Release bump, schema contract version tracking |
| `ecims2/server/app/api/deps.py` | Auth dependencies, role gates, license gates | RBAC/license gating behavior updates |
| `ecims2/server/app/security/auth.py` | Password hash and JWT creation/validation | Auth format/policy update |
| `ecims2/server/app/security/mtls.py` | mTLS cert identity validation | Agent identity rules, cert checks |

### 5.2 API and domain orchestration

| File | Role | Change trigger |
| --- | --- | --- |
| `ecims2/server/app/api/routes.py` | All REST endpoint wiring and HTTP-level error mapping | New endpoint, status code mapping, request/response flow changes |
| `ecims2/server/app/schemas/*.py` | Pydantic request/response contracts | API payload shape changes |
| `ecims2/server/app/services/*.py` | Domain business logic (feature-wise services) | Real behavior changes (not just HTTP layer) |

### 5.3 Database and schema

| File | Role | Change trigger |
| --- | --- | --- |
| `ecims2/server/app/db/database.py` | SQLite schema creation, indexes, schema version table, additive ensure helpers | New table/column/index, migration-safe schema evolution |

Important note:
- Current migration approach mostly additive/idempotent DDL + ensure helpers + schema version update.
- Agar breaking schema change chahiye, to explicit migration strategy design karni hogi (sirf DDL append enough nahi hoga).

### 5.4 Important services by capability

| Service File | Capability |
| --- | --- |
| `agent_service.py`, `agent_command_service.py` | Agent registration/token validation + command queue operations |
| `event_service.py`, `alert_service.py` | Event ingest, baseline/alert handling |
| `user_service.py`, `rbac_service.py` | Users, roles, account lifecycle |
| `feature_flag_service.py` | Feature/kill-switch style flags |
| `remote_action_task_service.py` | Remote action task lifecycle |
| `maintenance_schedule_service.py` | Maintenance windows and scheduler runs |
| `enrollment_service.py` | Online/offline enrollment token workflows |
| `evidence_vault_service.py` | Evidence object + custody chain |
| `playbook_service.py` | Playbook templates and approval/run dispatch |
| `change_control_service.py` | Change request approval workflow |
| `break_glass_service.py` | Emergency privileged sessions |
| `state_backup_service.py` | Backup snapshot and restore preview/apply |
| `patch_update_service.py` | Patch package upload, indexing, retrieval, status marking |
| `device_policy_service.py`, `device_control_state_service.py`, `device_allow_token_service.py` | Device control policies, state, allow-token issue/revoke |
| `audit_service.py` | Centralized audit entry writes |

---

## 6. Agent Core File Responsibility

| File | Role | Change trigger |
| --- | --- | --- |
| `ecims2/agent/ecims_agent/main.py` | Main runtime loop: register/enroll, scan, events, heartbeat, command polling | Agent flow order, polling cadence, runtime behavior |
| `config.py` | Agent config schema and parser | New agent config knobs |
| `runtime.py` | Runtime-id state isolation, lock file, state path wiring | Multi-agent isolation behavior changes |
| `scanner.py` | File/config scan event generation | Integrity detection behavior changes |
| `api_client.py` | Agent-server transport, TLS/pinning, endpoint calls | API contract or TLS handshake behavior change |
| `device_control.py` | Command processing, block/unblock, allow-token consume, offline queue | USB/device control behavior changes |
| `device_adapter.py` | OS-specific device block/unblock implementation | Platform enforcement logic changes |
| `offline_store.py`, `storage.py` | Local state/token/event queue persistence | Local durability behavior changes |
| `client_gui.py` | Endpoint operator GUI + runtime interactions | GUI control flow and operator UX |

---

## 7. Admin Console Core File Responsibility

| File | Role | Change trigger |
| --- | --- | --- |
| `ecims_admin/src/App.tsx` | Route map and lazy page loading | New page route, route-level access changes |
| `ecims_admin/src/layout/Sidebar.tsx` | Navigation structure | Menu group changes |
| `ecims_admin/src/layout/Topbar.tsx` | Search shortcuts/session widgets/theme controls | Header interactions |
| `ecims_admin/src/layout/AppLayout.tsx` | Global shell, session timeout, alert alarm modal | Layout-level behavior |
| `ecims_admin/src/api/client.ts` | Axios client, auth interceptor, base URL | API transport behavior |
| `ecims_admin/src/api/services.ts` | Backend endpoint binding layer for UI | New API integration or payload changes |
| `ecims_admin/src/types/index.ts` | Shared TS contract types | Response/request field updates |
| `ecims_admin/src/pages/...` | Feature pages and user workflows | Feature-specific UX/functionality changes |

Ops pages location:
- `ecims_admin/src/pages/ops/`

Admin pages location:
- `ecims_admin/src/pages/admin/`

---

## 8. Packaging and Release File Responsibility

| File | Responsibility |
| --- | --- |
| `ecims2/scripts/build_windows_executables.cmd` | Server EXE + Agent EXE + Client GUI EXE build, admin frontend bundling, zip outputs |
| `ecims2/scripts/templates/start_server_exe.cmd` | Packaged server startup wrapper and discovery URL handling |
| `ecims2/scripts/templates/start_agent_exe.cmd` | Packaged headless agent startup wrapper |
| `ecims2/scripts/templates/start_client_gui_exe.cmd` | Packaged client GUI startup wrapper |
| `ecims2/server/run_server_exe.py` | Server EXE runtime bootstrapping and default env path wiring |
| `ecims2/agent/run_agent_exe.py` | Agent EXE entrypoint |
| `ecims2/agent/run_client_gui_exe.py` | Client GUI EXE entrypoint |
| `ecims2/scripts/build_server_package.sh` | Non-EXE server ops package creation |
| `ecims2/scripts/build_agent_windows_package.sh` | Non-EXE Windows agent package creation |
| `ecims2/scripts/tag_release.sh` | Annotated release tagging helper |
| `ecims2/RELEASE.md` | Release checklist, backup, rotation, recovery guidance |

---

## 9. License and Trust Tooling Responsibility

| Path | Role |
| --- | --- |
| `license_authority/generate_keys.py` | Offline root keypair generation |
| `license_authority/generate_license.py` | Signed license artifact generation |
| `license_authority/generate_mtls_ca.py` | mTLS CA generation |
| `license_authority/sign_agent_csr.py` | Agent CSR signing |
| `license_authority_gui/la_gui/core/*` | GUI-driven secure artifact services (crypto, export, revocation, data-key) |

If question aaye "license invalid kyu" ya "mTLS identity chain kaha se trust hoti hai", answer generally in these folders milega.

---

## 10. Core Execution Flows (Step-by-Step)

## 10.1 Server startup flow

1. `main.py` loads settings from `core/config.py`.
2. DB init via `db/database.py`.
3. Signed policy load/verify via licensing core.
4. Startup guardrails validate weak secrets/policy/keys.
5. License load and gate state set.
6. Bootstrap admin logic (`user_service.py`) if needed.
7. Maintenance scheduler and discovery service start.
8. API router mount + admin frontend static mount.

## 10.2 Agent runtime flow

1. `main.py` load config + resolve server URL (discovery fallback possible).
2. Runtime context create (`runtime.py`) -> isolated folder by runtime id.
3. Register/enroll with server if state missing.
4. Scan paths -> post events.
5. Detect USB mass-storage -> policy flow in `device_control.py`.
6. Poll commands -> apply/ack.
7. Post device status + heartbeat.
8. On network issues -> local queue + replay.

## 10.3 Admin UI data flow

1. Page component -> `CoreApi.*` method (`services.ts`).
2. Axios client (`client.ts`) injects bearer token.
3. Backend route in `routes.py` calls service layer.
4. Service updates DB and audit.
5. UI refreshes via list endpoints.

## 10.4 Patch update flow

1. Admin uploads patch bundle (`POST /admin/ops/patch-updates/upload`).
2. `PatchUpdateService.upload_patch` stores file in `ecims2/server/patch_updates/` and DB row in `patch_updates` table.
3. Target machine downloads package (`GET .../download`).
4. Installer/script patch local machine par run hota hai (outside server).
5. Admin "Apply" action trigger karta hai (`POST .../apply`).
6. Server pre-change backup snapshot create karta hai (`StateBackupService.create_backup`).
7. Patch row `APPLIED` mark hota hai + audit log entry.

Critical truth:
- Current design me server direct binary auto-push nahi karta; rollout intentionally controlled/manual + auditable hai.

---

## 11. "Agar Yeh Change Karna Hai To Kahan Se Karna Hai" Playbook

## 11.1 New backend feature add karni hai

1. Request/response model `server/app/schemas/*.py` me add/update karo.
2. Business logic `server/app/services/<domain>_service.py` me implement karo.
3. Endpoint wire `server/app/api/routes.py` me karo.
4. DB table/column needed ho to `server/app/db/database.py` update karo.
5. Unit/integration tests `server/tests/` me add karo.
6. Frontend binding `ecims_admin/src/api/services.ts` + `types/index.ts` + संबंधित page me karo.

## 11.2 Existing endpoint behavior change

1. Pehle service file identify karo (routes imports se).
2. HTTP status/detail mapping agar badalna ho to `routes.py` ke `_raise_*_error` helpers update karo.
3. Contract breaking ho to schemas + frontend types dono update karo.

## 11.3 UI page logic change

1. संबंधित page file edit (`ecims_admin/src/pages/...`).
2. API call exists? `api/services.ts` check karo.
3. Type mismatch? `types/index.ts` update karo.
4. Navigation change? `App.tsx` / `Sidebar.tsx` update karo.

## 11.4 Agent command type add karna

1. Server side command enqueue logic where needed (`agent_command_service.py` or domain service).
2. Route/service se new command emit karo.
3. Agent side `device_control.py` (or relevant agent module) me command handler branch add karo.
4. Ack/status semantics align karo (`/agents/{id}/commands/{cmd}/ack`).
5. Tests: server + agent दोनों side add karo.

## 11.5 Security policy field add/modify

1. `configs/security.policy.json` and policy loader/validator logic update karo.
2. Service usage points update karo (`device_policy_service.py`, related checks).
3. Admin status endpoints and UI surfaces align karo.
4. Signed policy artifact regenerate karo (`security.policy.sig`).

## 11.6 Auth / RBAC change

1. `api/deps.py` role gates update karo.
2. `services/rbac_service.py` permission matrix update karo.
3. `schemas/user.py` and admin UI role pages verify/update karo.
4. `test_phase6_auth_rbac.py` and related tests update karo.

## 11.7 DB schema change safely

1. New DDL/index `database.py` me additive style add karo.
2. Ensure helper function approach use karo for old DB compatibility.
3. `SCHEMA_VERSION` bump decision carefully lo (`core/version.py`).
4. `test_schema_migration_guard.py` update/add assertions.
5. Existing data-preserving behavior validate karo.

---

## 12. Patch and Update Lifecycle (Developer -> End User)

## Stage A: Developer/producer side

1. Feature/fix implement in repo.
2. Relevant tests pass karo:
   - `make test-current`
   - `make test-security`
   - Agent tests
   - Admin build
3. Package build karo:
   - Windows EXE: `scripts\build_windows_executables.cmd`
4. Patch bundle prepare karo (zip or vendor installer package).

## Stage B: ECIMS server intake

1. Admin Console -> Patch Updates page -> upload bundle.
2. Metadata store hoti hai:
   - patch id
   - version
   - filename
   - sha256
   - status
3. File server patch vault me persist hoti hai.

## Stage C: Target environment deployment

1. Endpoint/LAN operator patch package download karta hai.
2. Package local host par apply karta hai (controlled window).
3. Admin "Apply" action use karta hai:
   - pre-change backup snapshot automatically create hota hai
   - patch status `APPLIED` mark hota hai
   - audit trail close hota hai

## Stage D: Rollback if required

1. Backup ID se restore preview run karo.
2. Risk evaluate karo.
3. Restore apply karo (controlled change window).
4. Audit export attach karo incident/change ticket me.

Current architecture rationale:
- Auto-force push avoid kiya gaya hai to reduce blast radius.
- Human-controlled apply + pre-change backup keeps recovery deterministic.

---

## 13. Developer Decision Rationale (Why These Choices)

## 13.1 FastAPI + Python backend

Why chosen:
- Rapid secure API development
- Strong typing via Pydantic
- Good fit for ops/security scripting + crypto integrations

Could be better alternative?
- Node/Go possible hain high-concurrency cases ke liye.

Why not chosen here:
- Existing team velocity + feature breadth + offline tooling ecosystem Python me stronger tha.

## 13.2 SQLite as current DB

Why chosen:
- Offline/LAN, simple deployment
- No separate DB service dependency
- Backup/restore straightforward

Could be better alternative?
- PostgreSQL for high concurrency and large scale.

Why not yet:
- Deployment simplicity and air-gapped operability first priority thi.

## 13.3 React + Vite admin UI

Why chosen:
- Fast development loop
- Clean API-driven modular pages
- Easy bundling into server package

Could be better alternative?
- Next.js enterprise stack ya heavier component framework.

Why not yet:
- Static bundled control-plane UI with minimal hosting complexity target tha.

## 13.4 EXE packaging via PyInstaller

Why chosen:
- Windows-first operational reality
- Shareable single-binary style deployments
- Easy 2-PC LAN rollout

Could be better alternative?
- MSI installer pipelines, containers, or code-signed enterprise deployment tools.

Why not yet:
- Current phase ka goal quick deploy + controlled offline distribution tha.

## 13.5 Manual patch apply workflow

Why chosen:
- Risk-controlled rollout in sensitive environments
- Mandatory audit and pre-change snapshot linkage

Could be better alternative?
- Fully automated OTA orchestration.

Why not yet:
- Offline/LAN + governance-centric model me manual control safer default hai.

---

## 14. Tough Review Questions and Suggested Answers

### Q1: "Aapne SQLite kyun choose kiya?"
Answer:
- Is project ka primary target offline/LAN controlled deployment hai, jahan dependency minimization critical tha. SQLite ne zero external DB dependency di aur deterministic backup/restore simplify kiya.

### Q2: "Agar scale badh gaya to?"
Answer:
- Service layer and API contracts modular hain. DB backend abstraction currently thin hai, lekin migration path PostgreSQL ki taraf possible hai with planned migration layer.

### Q3: "Patch auto-push kyun nahi?"
Answer:
- Security-sensitive endpoints me forced auto-push blast radius badhata hai. ECIMS ne controlled workflow choose kiya: upload -> manual target install -> apply mark + backup trail.

### Q4: "Offline environment me trust kaise maintain hota hai?"
Answer:
- Signed policy, offline license signatures, allow-token signatures, optional mTLS identity checks, and strict startup guardrails.

### Q5: "Agar admin credential compromise ho jaye?"
Answer:
- RBAC separation, audit trails, reason-based critical actions, break-glass and change-control model, plus key/policy artifact controls. Further improvement: MFA and external IdP integration roadmap.

### Q6: "Kya ECIMS full SIEM/EDR replacement hai?"
Answer:
- Nahi. ECIMS core strength endpoint integrity + operational governance + offline-safe controls hai. Broad SOC analytics ke liye complementary SIEM/EDR integration ideal hai.

---

## 15. Safe Change Workflow (Engineering SOP)

1. Problem statement clear define karo.
2. Impact area map karo:
   - API
   - Service
   - DB
   - Agent
   - UI
3. Contract first update karo (schemas/types).
4. Service logic implement karo.
5. Routes and UI binding integrate karo.
6. Tests add/update karo.
7. Local end-to-end smoke run karo.
8. Package build validate karo.
9. Patch workflow rehearsal karo.
10. Handover note and rollback plan update karo.

---

## 16. Testing and Validation Map

## Backend tests

Location:
- `ecims2/server/tests/`

Key suites examples:
- Auth/RBAC: `test_phase6_auth_rbac.py`
- Device enforcement: `test_phase8_device_enforcement_pilot.py`
- Ops control plane: `test_phase15_ops_control_plane.py`
- Patch updates: `test_phase17_patch_updates.py`
- Migration guard: `test_schema_migration_guard.py`

Run gates:
```bash
cd ecims2
make test-current
make test-security
```

## Agent tests

Location:
- `ecims2/agent/tests/`

Examples:
- `test_runtime_state_isolation.py`
- `test_device_control_pilot.py`
- `test_auto_discovery.py`

## Admin UI validation

Build check:
```bash
cd ecims_admin
npm run build
```

---

## 17. Handover Checklist (Producer/Developer)

1. Architecture walkthrough demo ready?
2. Core file ownership map understood?
3. Top 5 flows live demo kiye?
4. Patch upload->download->apply->rollback rehearsal complete?
5. Security artifacts and key ownership clarified?
6. Release and rollback commands documented?
7. Pending known risks and roadmap shared?

If above yes, handover quality strong mana jayega.

---

## 18. Current Known Gaps and Future Improvement Opportunities

1. DB scalability path (SQLite to PostgreSQL migration design doc).
2. More formal migration framework (versioned migration scripts).
3. Linux device enforcement parity improvements.
4. Stronger identity model (MFA/SSO) for admin console.
5. Optional automated patch orchestration with staged approvals.
6. Centralized observability stack integration for larger SOC estates.

---

## 19. Quick "Where to Look First" Index

| Need | First file to open |
| --- | --- |
| API not behaving as expected | `ecims2/server/app/api/routes.py` |
| Business logic bug | संबंधित `ecims2/server/app/services/*.py` |
| DB column/table issue | `ecims2/server/app/db/database.py` |
| Auth issue | `ecims2/server/app/api/deps.py`, `security/auth.py` |
| Agent runtime issue | `ecims2/agent/ecims_agent/main.py` |
| Device control behavior | `ecims2/agent/ecims_agent/device_control.py`, `server/app/services/device_*` |
| Admin page API mismatch | `ecims_admin/src/api/services.ts`, `src/types/index.ts` |
| UI route/menu issue | `ecims_admin/src/App.tsx`, `src/layout/Sidebar.tsx` |
| EXE package issue | `ecims2/scripts/build_windows_executables.cmd` |
| Patch workflow issue | `server/app/services/patch_update_service.py`, `routes.py`, `ecims_admin/src/pages/ops/PatchUpdatesPage.tsx` |

---

## 20. Final Note

Agar aap is project ko confidently present karna chahte ho, to teen cheezein crystal clear honi chahiye:

1. **Data flow** (Agent -> Server -> Admin -> Ops action -> Audit)
2. **Ownership map** (feature kis file family me rehta hai)
3. **Operational safety loop** (backup before risky change, auditable apply, deterministic rollback)

Yeh manual isi teen pillars ko production-handover perspective se cover karta hai.
