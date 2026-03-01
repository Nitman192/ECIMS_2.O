# License Authority GUI (ECIMS 2.0)

> **Phase 2 status:** Desktop PySide6 shell implemented and wired to Phase 1 core services.

## Offline Security Rules

- This tool is designed for an offline Windows workstation.
- Do not connect the License Authority workstation to external networks.
- Root private keys remain encrypted at rest and are never exported.
- Only public keys and signed artifacts are exportable.
- All signing actions are logged in an append-only audit log with hash chaining.

## Storage Layout

```text
license_authority_gui/
  keys/      # encrypted root key + public key
  logs/      # audit_log.jsonl hash-chained entries
  exports/   # signed artifacts and operator exports
  config/    # local application settings
```

## Phase 2 Implemented GUI Pages

- Dashboard: storage path visibility, root key presence, last audit actions.
- Root Key Management: generate, unlock, lock, fingerprint display, public key export.
- License Signing: form input, preview canonical payload, confirm + sign, file verification.
- Revocation: serial entry, signed bundle generation, bundle verification.
- Audit Log: list entries, verify chain, export copy.
- mTLS CA Management and Data Key Bundles placeholders marked for Phase 3.

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

## Upcoming Phases

- **Phase 3:** mTLS CA issuance workflows, data key bundle workflows, secure export bundles.
- **Phase 4:** hardening checklist, PyInstaller packaging guide, final QA.
