@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe
  echo [HINT] Run: python -m venv .venv
  exit /b 1
)

set "PYTHON=.venv\Scripts\python.exe"
set "BUILD_ROOT=%CD%\build\windows_executables"
set "PYI_WORK=%BUILD_ROOT%\work"
set "PYI_SPEC=%BUILD_ROOT%\spec"
set "PYI_DIST=%BUILD_ROOT%\dist"
set "OUT_ROOT=%CD%\dist\windows_executables"
set "OUT_SERVER=%OUT_ROOT%\server"
set "OUT_CLIENT=%OUT_ROOT%\client"
set "OUT_ACTIVATION=%OUT_ROOT%\activation"
set "ADMIN_ROOT=%CD%\..\ecims_admin"
set "ADMIN_DIST=%ADMIN_ROOT%\dist"
set "LA_ROOT=%CD%\..\license_authority_gui"

if not exist "%ADMIN_ROOT%\package.json" (
  echo [ERROR] Admin frontend project not found at %ADMIN_ROOT%
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm is required to build admin frontend but was not found in PATH
  exit /b 1
)

echo [INFO] Building admin frontend...
pushd "%ADMIN_ROOT%"
if not exist "node_modules" (
  echo [INFO] Installing admin frontend dependencies...
  call npm install
  if errorlevel 1 (
    popd
    echo [ERROR] npm install failed for admin frontend
    exit /b 1
  )
)
set "VITE_API_BASE_URL=/api/v1"
call npm run build
if errorlevel 1 (
  popd
  echo [ERROR] Admin frontend build failed
  exit /b 1
)
popd

if not exist "%ADMIN_DIST%\index.html" (
  echo [ERROR] Admin frontend dist was not generated at %ADMIN_DIST%
  exit /b 1
)

echo [INFO] Installing/updating PyInstaller in project venv...
"%PYTHON%" -m pip install --upgrade pyinstaller
if errorlevel 1 (
  echo [ERROR] Failed to install PyInstaller
  exit /b 1
)

echo [INFO] Syncing server and agent dependencies...
"%PYTHON%" -m pip install -r server\requirements.txt -r agent\requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed to install project dependencies in venv
  exit /b 1
)

if exist "%BUILD_ROOT%" rmdir /s /q "%BUILD_ROOT%"
if exist "%OUT_ROOT%" rmdir /s /q "%OUT_ROOT%"

mkdir "%PYI_WORK%" >nul
mkdir "%PYI_SPEC%" >nul
mkdir "%PYI_DIST%" >nul
mkdir "%OUT_SERVER%" >nul
mkdir "%OUT_CLIENT%" >nul
mkdir "%OUT_ACTIVATION%" >nul

echo [INFO] Building server executable...
"%PYTHON%" -m PyInstaller --noconfirm --clean --onefile --name ecims_server ^
  --paths server ^
  --hidden-import app.main ^
  --hidden-import uvicorn.loops.asyncio ^
  --hidden-import uvicorn.protocols.http.h11_impl ^
  --workpath "%PYI_WORK%\server" ^
  --specpath "%PYI_SPEC%\server" ^
  --distpath "%PYI_DIST%\server" ^
  server\run_server_exe.py
if errorlevel 1 (
  echo [ERROR] Server executable build failed
  exit /b 1
)

echo [INFO] Building agent executable...
"%PYTHON%" -m PyInstaller --noconfirm --clean --onefile --name ecims_agent ^
  --paths agent ^
  --collect-submodules ecims_agent ^
  --workpath "%PYI_WORK%\agent" ^
  --specpath "%PYI_SPEC%\agent" ^
  --distpath "%PYI_DIST%\agent" ^
  agent\run_agent_exe.py
if errorlevel 1 (
  echo [ERROR] Agent executable build failed
  exit /b 1
)

echo [INFO] Building client GUI executable...
"%PYTHON%" -m PyInstaller --noconfirm --clean --onefile --windowed --name ecims_client_gui ^
  --paths agent ^
  --collect-submodules ecims_agent ^
  --workpath "%PYI_WORK%\client_gui" ^
  --specpath "%PYI_SPEC%\client_gui" ^
  --distpath "%PYI_DIST%\client_gui" ^
  agent\run_client_gui_exe.py
if errorlevel 1 (
  echo [ERROR] Client GUI executable build failed
  exit /b 1
)

copy /Y "%PYI_DIST%\server\ecims_server.exe" "%OUT_SERVER%\ecims_server.exe" >nul
copy /Y "%PYI_DIST%\agent\ecims_agent.exe" "%OUT_CLIENT%\ecims_agent.exe" >nul
copy /Y "%PYI_DIST%\client_gui\ecims_client_gui.exe" "%OUT_CLIENT%\ecims_client_gui.exe" >nul

copy /Y "scripts\templates\start_server_exe.cmd" "%OUT_SERVER%\start_server.cmd" >nul
copy /Y "scripts\templates\start_agent_exe.cmd" "%OUT_CLIENT%\start_agent.cmd" >nul
copy /Y "scripts\templates\start_client_gui_exe.cmd" "%OUT_CLIENT%\start_client_gui.cmd" >nul

if exist "%OUT_SERVER%\admin_frontend" rmdir /s /q "%OUT_SERVER%\admin_frontend"
xcopy /E /I /Y "%ADMIN_DIST%\*" "%OUT_SERVER%\admin_frontend\" >nul
if errorlevel 1 (
  echo [ERROR] Failed to copy admin frontend build into server package
  exit /b 1
)

mkdir "%OUT_SERVER%\configs" >nul
mkdir "%OUT_CLIENT%\configs" >nul
mkdir "%OUT_CLIENT%\.ecims_agent_runtime" >nul

if exist "configs\server.yaml.template" copy /Y "configs\server.yaml.template" "%OUT_SERVER%\configs\server.yaml.template" >nul
if exist "configs\server.yaml" copy /Y "configs\server.yaml" "%OUT_SERVER%\configs\server.yaml" >nul
if exist "configs\license.ecims" copy /Y "configs\license.ecims" "%OUT_SERVER%\configs\license.ecims" >nul
if exist "configs\security.policy.json" copy /Y "configs\security.policy.json" "%OUT_SERVER%\configs\security.policy.json" >nul
if exist "configs\security.policy.sig" copy /Y "configs\security.policy.sig" "%OUT_SERVER%\configs\security.policy.sig" >nul
if exist "configs\security.policy.public.pem" copy /Y "configs\security.policy.public.pem" "%OUT_SERVER%\configs\security.policy.public.pem" >nul
if exist "configs\device_allow_token_public.pem" copy /Y "configs\device_allow_token_public.pem" "%OUT_SERVER%\configs\device_allow_token_public.pem" >nul
if exist "configs\device_allow_token_private.pem" copy /Y "configs\device_allow_token_private.pem" "%OUT_SERVER%\configs\device_allow_token_private.pem" >nul
if exist ".env.production.template" copy /Y ".env.production.template" "%OUT_SERVER%\.env.production.template" >nul

if exist "configs\agent.local.dev.yaml" copy /Y "configs\agent.local.dev.yaml" "%OUT_CLIENT%\configs\agent.local.dev.yaml" >nul
if exist "configs\agent.yaml" copy /Y "configs\agent.yaml" "%OUT_CLIENT%\configs\agent.yaml" >nul
if exist "configs\device_allow_token_public.pem" copy /Y "configs\device_allow_token_public.pem" "%OUT_CLIENT%\configs\device_allow_token_public.pem" >nul

> "%OUT_SERVER%\README-RUN.txt" (
  echo ECIMS Server EXE Package
  echo.
  echo 1^) Optional: edit configs\server.yaml
  echo 2^) Start: start_server.cmd
  echo 3^) Health: curl.exe http://127.0.0.1:8010/health
  echo 4^) Admin Console: http://127.0.0.1:8010/
)

> "%OUT_CLIENT%\README-RUN.txt" (
  echo ECIMS Client EXE Package
  echo.
  echo 1^) Optional: edit configs\agent.local.dev.yaml
  echo 2^) Start GUI: start_client_gui.cmd client-a
  echo 3^) Start headless agent: start_agent.cmd client-a
)

if exist "%LA_ROOT%\app.py" (
  echo [INFO] Building License Authority activation app executable...
  pushd "%LA_ROOT%"
  powershell -NoProfile -ExecutionPolicy Bypass -File ".\packaging\build_windows.ps1" -UseSpec
  if errorlevel 1 (
    popd
    echo [ERROR] License Authority executable build failed
    exit /b 1
  )
  popd
  if not exist "%LA_ROOT%\dist\ECIMS_License_Authority.exe" (
    echo [ERROR] License Authority executable not found after build
    exit /b 1
  )
  copy /Y "%LA_ROOT%\dist\ECIMS_License_Authority.exe" "%OUT_ACTIVATION%\ECIMS_License_Authority.exe" >nul
  > "%OUT_ACTIVATION%\README-RUN.txt" (
    echo ECIMS Activation App EXE Package
    echo.
    echo 1^) Start ECIMS_License_Authority.exe on offline licensing workstation.
    echo 2^) Use Server Activation page to convert server request_code into verification ID.
    echo 3^) Paste verification ID back on target server.
  )
) else (
  echo [WARN] license_authority_gui not found. Skipping activation app package.
)

set "SERVER_ZIP=%OUT_ROOT%\ecims_server_windows.zip"
set "CLIENT_ZIP=%OUT_ROOT%\ecims_client_windows.zip"
set "ACTIVATION_ZIP=%OUT_ROOT%\ecims_activation_app_windows.zip"
if exist "%SERVER_ZIP%" del /f /q "%SERVER_ZIP%" >nul
if exist "%CLIENT_ZIP%" del /f /q "%CLIENT_ZIP%" >nul
if exist "%ACTIVATION_ZIP%" del /f /q "%ACTIVATION_ZIP%" >nul

powershell -NoProfile -Command "Compress-Archive -Path '%OUT_SERVER%\\*' -DestinationPath '%SERVER_ZIP%' -Force"
if errorlevel 1 (
  echo [ERROR] Failed to create server zip archive
  exit /b 1
)
powershell -NoProfile -Command "Compress-Archive -Path '%OUT_CLIENT%\\*' -DestinationPath '%CLIENT_ZIP%' -Force"
if errorlevel 1 (
  echo [ERROR] Failed to create client zip archive
  exit /b 1
)
if exist "%OUT_ACTIVATION%\ECIMS_License_Authority.exe" (
  powershell -NoProfile -Command "Compress-Archive -Path '%OUT_ACTIVATION%\\*' -DestinationPath '%ACTIVATION_ZIP%' -Force"
  if errorlevel 1 (
    echo [ERROR] Failed to create activation app zip archive
    exit /b 1
  )
)

echo [DONE] Windows executable packages are ready:
echo        %OUT_SERVER%
echo        %OUT_CLIENT%
echo        %OUT_ACTIVATION%
echo        %SERVER_ZIP%
echo        %CLIENT_ZIP%
if exist "%ACTIVATION_ZIP%" echo        %ACTIVATION_ZIP%
echo [NEXT] Copy these folders to separate PCs and run start_*.cmd
exit /b 0
