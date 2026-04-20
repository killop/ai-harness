@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "WORKSPACE_ROOT=%%~fI"
set "MEMPALACE_REPO=%WORKSPACE_ROOT%\mempalace-github-code"
set "PALACE_PATH=%WORKSPACE_ROOT%\.mempalace_local\palace"
set "VENV_PYTHON=%MEMPALACE_REPO%\.venv\Scripts\python.exe"
set "SETUP_SCRIPT=%SCRIPT_DIR%Setup-MemPalace.ps1"

if not exist "%MEMPALACE_REPO%\mempalace\mcp_server.py" (
  echo MemPalace repo not found: %MEMPALACE_REPO% 1>&2
  exit /b 1
)

if not exist "%VENV_PYTHON%" (
  echo MemPalace venv not found: %VENV_PYTHON% 1>&2
  echo Run: powershell -ExecutionPolicy Bypass -File "%SETUP_SCRIPT%" 1>&2
  exit /b 1
)

if not exist "%PALACE_PATH%" (
  mkdir "%PALACE_PATH%" 1>nul 2>nul
)

cd /d "%MEMPALACE_REPO%"
"%VENV_PYTHON%" -m mempalace.mcp_server --palace "%PALACE_PATH%"
