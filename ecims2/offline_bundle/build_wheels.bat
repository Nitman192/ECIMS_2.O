@echo off
setlocal enabledelayedexpansion

REM Build ECIMS offline wheel bundle on an internet-connected Windows machine.

set "ROOT_DIR=%~dp0.."
for %%I in ("%ROOT_DIR%") do set "ROOT_DIR=%%~fI"
set "BUNDLE_DIR=%ROOT_DIR%\offline_bundle"
set "WHEELHOUSE_DIR=%BUNDLE_DIR%\wheelhouse"
set "LOCK_SERVER=%BUNDLE_DIR%\requirements_server.lock.txt"
set "LOCK_AGENT=%BUNDLE_DIR%\requirements_agent.lock.txt"
set "TMP_DIR=%BUNDLE_DIR%\.tmp_build"

if "%PYTHON_BIN%"=="" set "PYTHON_BIN=python"

echo [1/4] Cleaning wheelhouse and temp directories
if exist "%WHEELHOUSE_DIR%" rmdir /s /q "%WHEELHOUSE_DIR%"
if exist "%TMP_DIR%" rmdir /s /q "%TMP_DIR%"
mkdir "%WHEELHOUSE_DIR%"
mkdir "%TMP_DIR%"

echo [2/4] Resolving and pinning server lock file
call :resolve_lock "%ROOT_DIR%\server\requirements.txt" "%LOCK_SERVER%" "%TMP_DIR%\venv_server"
if errorlevel 1 exit /b 1

echo [3/4] Resolving and pinning agent lock file
call :resolve_lock "%ROOT_DIR%\agent\requirements.txt" "%LOCK_AGENT%" "%TMP_DIR%\venv_agent"
if errorlevel 1 exit /b 1

echo [4/4] Downloading wheels
%PYTHON_BIN% -m pip download --only-binary=:all: -r "%ROOT_DIR%\server\requirements.txt" -d "%WHEELHOUSE_DIR%" || exit /b 1
%PYTHON_BIN% -m pip download --only-binary=:all: -r "%ROOT_DIR%\agent\requirements.txt" -d "%WHEELHOUSE_DIR%" || exit /b 1
%PYTHON_BIN% -m pip download --only-binary=:all: -r "%LOCK_SERVER%" -d "%WHEELHOUSE_DIR%" || exit /b 1
%PYTHON_BIN% -m pip download --only-binary=:all: -r "%LOCK_AGENT%" -d "%WHEELHOUSE_DIR%" || exit /b 1
%PYTHON_BIN% -m pip download --only-binary=:all: pip setuptools wheel -d "%WHEELHOUSE_DIR%" || exit /b 1
%PYTHON_BIN% -m pip download --only-binary=:all: PyYAML -d "%WHEELHOUSE_DIR%" || exit /b 1

if exist "%TMP_DIR%" rmdir /s /q "%TMP_DIR%"
echo Done. Wheelhouse and lock files are ready.
exit /b 0

:resolve_lock
set "REQ_FILE=%~1"
set "OUT_LOCK=%~2"
set "ENV_DIR=%~3"

if exist "%ENV_DIR%" rmdir /s /q "%ENV_DIR%"
%PYTHON_BIN% -m venv "%ENV_DIR%" || exit /b 1
call "%ENV_DIR%\Scripts\activate.bat" || exit /b 1
python -m pip install --upgrade pip setuptools wheel || exit /b 1
python -m pip install -r "%REQ_FILE%" || exit /b 1
python -m pip freeze --exclude-editable > "%OUT_LOCK%" || exit /b 1
call deactivate
exit /b 0
