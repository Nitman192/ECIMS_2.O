# License Authority GUI (ECIMS 2.0)

> **Phase 4 status:** Hardening layer, diagnostics export, packaging assets, and Quick Start (Wizard) mode implemented.  
> **Phase 3 status:** Activation bundles, mTLS CA workflows, and data key bundle rotation implemented.  
> **Phase 2 status:** Desktop PySide6 GUI wired to Phase 1 core cryptographic services.

---

## Offline Security Rules

- This tool is designed for an offline Windows workstation.
- Do not connect the License Authority workstation to external networks.
- Root and mTLS CA private keys remain encrypted at rest and are never exported.
- Only public keys and signed artifacts are exportable.
- All sensitive actions are logged in append-only audit log entries with hash chaining.

---

## Storage Layout
license_authority_gui/
keys/ (encrypted LA root key, encrypted mTLS CA key, public certs)
logs/ (audit_log.jsonl hash-chained entries)
exports/ (signed artifacts and activation bundles)
config/ (app_settings.json, offline_ack.json, latest_data_key_bundle.json)

---

# Phase 4 — Hardening + Wizard Mode

## Operator Safety Controls

config/app_settings.json is auto-created with defaults:

- require_offline_ack: true
- show_advanced_mode: true
- confirm_sensitive_actions: true
- lock_on_idle_seconds: 300

Security features:

- Offline acknowledgement enforced and persisted in config/offline_ack.json
- Idle lock monitors keyboard/mouse activity and locks in-memory key state after timeout
- Status bar includes visible LOCK button and security indicators
- Sensitive actions require confirmation (configurable policy)

---

## Diagnostics Export (Offline-Safe)

Tools → Export Diagnostics generates:

exports/diagnostics_<timestamp>.zip

Includes only non-secret files:

- config/app_settings.json
- config/offline_ack.json (if present)
- config/latest_data_key_bundle.json (if present)
- logs/audit_log.jsonl
- README.md

keys/ directory is never included.

---

## Quick Start (Wizard)

- Guided workflow with progress indicator and prerequisite gating
- Each step shows status: OK / Missing / Locked / Needs Input
- If show_advanced_mode=false, app shows only Wizard + Audit Log
- If true, full advanced navigation remains available

---

# Phase 3 — Core Operational Features

## Activation Export Bundles

Dashboard → Export Activation Bundle

Creates:

activation_bundle_<timestamp>.zip

Includes:

- Required: license.json, la_public_key.pem
- Optional: mtls_ca_cert.pem, mtls_chain.pem, revocation.json, data_key_bundle.json
- manifest.json with SHA-256 hashes + manifest_sha256

Manifest is verified immediately after bundle creation.

---

## mTLS CA Management

- Generate encrypted CA private key + CA certificate in keys/
- Sign agent CSR PEM files
- Export:
  - exports/mtls_chain.pem
  - exports/mtls_ca_cert.pem

---

## Data Key Bundles

- Generate and rotate data key bundles
- Latest bundle saved in config/latest_data_key_bundle.json
- Exported copy saved as exports/data_key_bundle.json

---

# Operational SOP

1. Acknowledge offline policy.
2. Generate or unlock root key.
3. Issue license.
4. (Optional) Generate mTLS CA and sign agent CSR.
5. (Optional) Generate or rotate data key bundle.
6. (Optional) Generate revocation bundle.
7. Export activation bundle.
8. Verify audit chain.
9. Transfer artifacts using trusted removable media only.

---

# Phase 2 — Implemented GUI Pages

- Dashboard
- Root Key Management
- License Signing
- Revocation
- Audit Log
- mTLS CA Management
- Data Key Bundles

---

# Development Run Commands
from repository root

python -m pip install -r license_authority_gui/requirements.txt
python -m pytest license_authority_gui/tests
cd license_authority_gui
python app.py

or

python -m la_gui


---

# Packaging

See PACKAGING.md and the packaging/ directory for:

- PyInstaller spec file
- Windows build PowerShell script
- Reproducible packaging instructions