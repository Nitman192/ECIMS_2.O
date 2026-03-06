@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe
  echo Create it first: python -m venv .venv
  exit /b 1
)

if "%~1"=="" (
  set "RUNTIME_IDS=client-a client-b"
) else (
  set "RUNTIME_IDS=%*"
)

for %%R in (%RUNTIME_IDS%) do (
  echo [INFO] Launching agent runtime: %%R
  start "ecims-agent-%%R" cmd /k "cd /d %CD% && scripts\run_agent_local_dev.cmd %%R"
)
