@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe
  echo Create it first: python -m venv .venv
  exit /b 1
)

for /f "tokens=5" %%p in ('netstat -ano ^| findstr LISTENING ^| findstr :8010') do (
  taskkill /F /PID %%p >nul 2>nul
)

set PYTHONPATH=server
set ECIMS_ENVIRONMENT=dev
set ECIMS_MTLS_ENABLED=0
set ECIMS_MTLS_REQUIRED=0
echo [INFO] Starting ECIMS server on http://127.0.0.1:8010
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
