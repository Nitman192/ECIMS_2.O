@echo off
setlocal
cd /d "%~dp0"

set "RUNTIME_ID=%~1"
if "%RUNTIME_ID%"=="" set "RUNTIME_ID=endpoint-local-dev"
set "ECIMS_CLIENT_GUI_RUNTIME_ID=%RUNTIME_ID%"

echo [INFO] Launching ECIMS Client GUI EXE (runtime=%RUNTIME_ID%)
ecims_client_gui.exe

