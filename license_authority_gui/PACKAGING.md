# Windows Packaging Guide (PyInstaller)

This application is offline-first and must be built without embedding operational secrets.

## 1) Create virtual environment

```powershell
cd license_authority_gui
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 2) Install build dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
```

## 3) Build executable

### Option A: quick onefile build

```powershell
pyinstaller --noconsole --name "ECIMS_License_Authority" --onefile app.py
```

### Option B: use provided spec

```powershell
pyinstaller .\packaging\ecims_license_authority.spec
```

## 4) Output location

- Executable is generated under `dist/`.
- No keys or runtime secrets are embedded by the build process.

## 5) Qt plugin notes

PyInstaller usually auto-collects required Qt plugins. If runtime plugin issues occur, use the spec file and include hidden imports as needed.

## Risk Mapping (Packaging + Ops)

| Area | Risk Level | Mitigation |
|---|---|---|
| Accidental key export | High | Diagnostics and packaging never include `keys/`; activation export only includes allowlisted public/signed artifacts. |
| Operator misuse | Medium | Sensitive actions can require confirmations via `config/app_settings.json`. |
| Idle exposure | Medium | Idle lock auto-purges in-memory key based on `lock_on_idle_seconds`. |
| Diagnostics leakage | Medium | Diagnostics snapshot excludes private key directory permanently. |
| Packaging mistakes | Medium | Use scripted PowerShell build and provided PyInstaller spec. |
