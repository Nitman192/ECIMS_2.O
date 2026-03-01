# License Authority GUI (ECIMS 2.0)

> **Phase 4 status:** Hardening, diagnostics export, packaging assets, and Quick Start wizard mode are implemented.

## Offline Security Rules

- This tool is designed for an offline Windows workstation.
- Do not connect the License Authority workstation to external networks.
- Root and mTLS CA private keys remain encrypted at rest and are never exported.
- Only public keys and signed artifacts are exportable.
- All sensitive actions are logged in append-only audit log entries with hash chaining.

## Storage Layout

```text
license_authority_gui/
  keys/      # encrypted LA root key, encrypted mTLS CA key, public certs
  logs/      # audit_log.jsonl hash-chained entries
  exports/   # signed artifacts and activation bundles
  config/    # app_settings.json, offline_ack.json, latest_data_key_bundle.json
```

## Phase 4 Hardening + Wizard Mode

### Operator safety controls
- `config/app_settings.json` is auto-created with defaults:
  - `require_offline_ack`: true
  - `show_advanced_mode`: true
  - `confirm_sensitive_actions`: true
  - `lock_on_idle_seconds`: 300
- Offline acknowledgement is enforced (if configured) and persisted in `config/offline_ack.json`.
- Idle lock monitors keyboard/mouse activity and locks in-memory key state after timeout.
- Status bar includes a visible **LOCK** button and security indicators.

### Diagnostics export (offline-safe)
- Tools → Export Diagnostics generates `exports/diagnostics_<timestamp>.zip`.
- Includes only non-secret files:
  - `config/app_settings.json`
  - `config/offline_ack.json` (if present)
  - `config/latest_data_key_bundle.json` (if present)
  - `logs/audit_log.jsonl`
  - `README.md`
- `keys/` is never included.

### Quick Start (Wizard)
- New **Quick Start (Wizard)** page provides guided workflow with progress indicator.
- If `show_advanced_mode=false`, app shows only Wizard + Audit Log.
- If true, Wizard is shown alongside all advanced pages.

## Activation Bundle Artifacts

`activation_bundle_<timestamp>.zip` includes:
- required: `license.json`, `la_public_key.pem`
- optional: `mtls_ca_cert.pem`, `mtls_chain.pem`, `revocation.json`, `data_key_bundle.json`
- `manifest.json` with file SHA-256 values + `manifest_sha256`

## Operational SOP

1. Acknowledge offline policy on startup.
2. Generate or unlock root key.
3. Issue license.
4. Optionally generate mTLS CA and sign agent CSR.
5. Optionally generate/rotate data key bundle.
6. Optionally generate revocation bundle.
7. Export activation bundle.
8. Verify audit chain.
9. Transfer artifacts using trusted removable media only.

## Packaging

See [PACKAGING.md](./PACKAGING.md) and `packaging/` scripts/spec for Windows PyInstaller builds.

## Development Run Commands

```bash
python -m pip install -r license_authority_gui/requirements.txt
python -m pytest license_authority_gui/tests
cd license_authority_gui
python app.py
# or
python -m la_gui
```
