param(
    [switch]$UseSpec = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    py -3 -m venv .venv
}

. .\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

if ($UseSpec) {
    pyinstaller .\packaging\ecims_license_authority.spec
} else {
    pyinstaller --noconsole --name "ECIMS_License_Authority" --onefile app.py
}

Write-Host "Build complete. Check .\dist\ for output binary."
