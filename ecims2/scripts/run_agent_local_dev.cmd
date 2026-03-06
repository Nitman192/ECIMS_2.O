@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe
  echo Create it first: python -m venv .venv
  exit /b 1
)

set PYTHONPATH=agent
set "RUNTIME_ID=%~1"
if "%RUNTIME_ID%"=="" set "RUNTIME_ID=endpoint-local-dev"
set "STATE_DIR=%CD%\.ecims_agent_runtime"
echo [INFO] Using config: %CD%\configs\agent.local.dev.yaml
echo [INFO] Runtime ID: %RUNTIME_ID%
echo [INFO] State dir: %STATE_DIR%
".venv\Scripts\python.exe" -m ecims_agent.main --config configs/agent.local.dev.yaml --runtime-id "%RUNTIME_ID%" --state-dir "%STATE_DIR%"
