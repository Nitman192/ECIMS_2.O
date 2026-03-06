@echo off
setlocal
cd /d "%~dp0"

if not exist "configs\server.yaml" (
  if exist "configs\server.yaml.template" copy /Y "configs\server.yaml.template" "configs\server.yaml" >nul
)

if not defined ECIMS_ENVIRONMENT set ECIMS_ENVIRONMENT=dev
if not defined ECIMS_DISCOVERY_ENABLED set ECIMS_DISCOVERY_ENABLED=1
if not defined ECIMS_SERVER_PORT set ECIMS_SERVER_PORT=8010
if not defined ECIMS_SERVER_HOST set ECIMS_SERVER_HOST=0.0.0.0

if not defined ECIMS_DISCOVERY_SERVER_URL (
  set "ECIMS_ADVERTISE_IP="
  for /f %%i in ('powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue ^| Where-Object { $_.IPAddress -notlike '169.254*' -and $_.IPAddress -ne '127.0.0.1' } ^| Select-Object -First 1 -ExpandProperty IPAddress)"') do (
    if not defined ECIMS_ADVERTISE_IP set "ECIMS_ADVERTISE_IP=%%i"
  )
  if not defined ECIMS_ADVERTISE_IP set "ECIMS_ADVERTISE_IP=127.0.0.1"
  set "ECIMS_DISCOVERY_SERVER_URL=http://%ECIMS_ADVERTISE_IP%:%ECIMS_SERVER_PORT%"
)

echo [INFO] Starting ECIMS Server EXE on %ECIMS_SERVER_HOST%:%ECIMS_SERVER_PORT%
echo [INFO] Discovery advertises: %ECIMS_DISCOVERY_SERVER_URL%
ecims_server.exe --host %ECIMS_SERVER_HOST% --port %ECIMS_SERVER_PORT% --environment %ECIMS_ENVIRONMENT%
