@echo off
setlocal
cd /d "%~dp0"

set "RUNTIME_ID=%~1"
if "%RUNTIME_ID%"=="" set "RUNTIME_ID=endpoint-local-dev"

echo [INFO] Launching ECIMS Agent EXE (runtime=%RUNTIME_ID%)
ecims_agent.exe --config configs/agent.local.dev.yaml --runtime-id "%RUNTIME_ID%" --state-dir ".ecims_agent_runtime"

