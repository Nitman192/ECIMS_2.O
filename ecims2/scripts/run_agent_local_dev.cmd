@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe
  echo Create it first: python -m venv .venv
  exit /b 1
)

set PYTHONPATH=agent
".venv\Scripts\python.exe" -m ecims_agent.main --config configs/agent.local.dev.yaml
