@echo off
setlocal

REM Install ECIMS dependencies from local wheelhouse only (offline/air-gapped).

set "ROOT_DIR=%~dp0.."
for %%I in ("%ROOT_DIR%") do set "ROOT_DIR=%%~fI"
set "VENV_DIR=%ROOT_DIR%\.venv"
set "WHEELHOUSE_DIR=%ROOT_DIR%\offline_bundle\wheelhouse"
set "LOCK_SERVER=%ROOT_DIR%\offline_bundle\requirements_server.lock.txt"
set "LOCK_AGENT=%ROOT_DIR%\offline_bundle\requirements_agent.lock.txt"

if "%PYTHON_BIN%"=="" set "PYTHON_BIN=python"

if not exist "%WHEELHOUSE_DIR%" (
  echo wheelhouse directory not found: %WHEELHOUSE_DIR%
  exit /b 1
)

if not exist "%LOCK_SERVER%" (
  echo Missing lock file: %LOCK_SERVER%
  exit /b 1
)

if not exist "%LOCK_AGENT%" (
  echo Missing lock file: %LOCK_AGENT%
  exit /b 1
)

if not exist "%VENV_DIR%" (
  echo Creating virtual environment at %VENV_DIR%
  %PYTHON_BIN% -m venv "%VENV_DIR%" || exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat" || exit /b 1
python -m pip install --no-index --find-links "%WHEELHOUSE_DIR%" --upgrade pip setuptools wheel || exit /b 1
python -m pip install --no-index --find-links "%WHEELHOUSE_DIR%" -r "%LOCK_SERVER%" || exit /b 1
python -m pip install --no-index --find-links "%WHEELHOUSE_DIR%" -r "%LOCK_AGENT%" || exit /b 1

echo Offline install complete.
