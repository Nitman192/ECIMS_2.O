@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe
  echo Create it first: python -m venv .venv
  exit /b 1
)

set "RUNTIME_ID=%~1"
if "%RUNTIME_ID%"=="" set "RUNTIME_ID=endpoint-local-dev"

set PYTHONPATH=agent
set ECIMS_CLIENT_GUI_RUNTIME_ID=%RUNTIME_ID%
echo [INFO] Launching client GUI for runtime: %RUNTIME_ID%
".venv\Scripts\python.exe" -m ecims_agent.client_gui
