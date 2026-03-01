# License Authority GUI (ECIMS 2.0)

> **Phase 3 status:** Activation bundles, mTLS CA workflows, and data key bundle rotation are implemented.

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
  config/    # local app settings + latest_data_key_bundle.json
```

## Phase 3 Features

### 1) Activation export bundles
- Dashboard includes **Export Activation Bundle**.
- Outputs `activation_bundle_<timestamp>.zip` to `exports/`.
- Bundle includes:
  - required: `license.json`, `la_public_key.pem`
  - optional: `mtls_ca_cert.pem`, `mtls_chain.pem`, `revocation.json`, `data_key_bundle.json`
- `manifest.json` includes SHA-256 for each included file and `manifest_sha256` for manifest core fields.
- Manifest is verified immediately after bundle creation.

### 2) mTLS CA management
- Generate encrypted CA private key + CA certificate in `keys/`.
- Sign agent CSR PEM files into agent certificates in `exports/`.
- Export chain as `exports/mtls_chain.pem` and `exports/mtls_ca_cert.pem`.

### 3) Data key bundles
- Generate and rotate data key bundles for server at-rest encryption workflows.
- Latest bundle is saved in `config/latest_data_key_bundle.json`.
- Exported copy is saved as `exports/data_key_bundle.json`.

## Operational SOP (Phase 3)

1. **Prepare keys:** Generate/unlock LA root key in Root Key Management.
2. **Issue license:** Use License Signing page (preview, confirm, sign).
3. **(Optional) mTLS enrollment:** Generate mTLS CA, then sign each agent CSR.
4. **(Optional) Data key setup:** Generate initial data key bundle or rotate existing one.
5. **(Optional) Revocation update:** Generate signed revocation bundle when needed.
6. **Create activation bundle:** Dashboard → Export Activation Bundle.
7. **Transfer artifacts:** Copy activation bundle via trusted removable media to the target server environment.
8. **Verify audit chain:** Run audit verification before and after export operations.

## Development Run Commands

```bash
# from repository root
python -m pip install -r license_authority_gui/requirements.txt
python -m pytest license_authority_gui/tests
cd license_authority_gui
python app.py
# or
python -m la_gui
```

## Upcoming Phase

- **Phase 4:** hardening checklist, PyInstaller packaging guide, final QA.
