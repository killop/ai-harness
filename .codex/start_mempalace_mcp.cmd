@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_ROOT=%%~fI"
set "WORKSPACE_ROOT=%PROJECT_ROOT%\harness-workspace"
set "MEMPALACE_REPO=%WORKSPACE_ROOT%\mempalace-github-code"
set "PALACE_PATH=%WORKSPACE_ROOT%\.mempalace_local\palace"

if not exist "%MEMPALACE_REPO%\mempalace\mcp_server.py" (
  echo MemPalace repo not found: %MEMPALACE_REPO% 1>&2
  exit /b 1
)

if not exist "%PALACE_PATH%" (
  mkdir "%PALACE_PATH%" 1>nul 2>nul
)

set "PYTHONPATH=%MEMPALACE_REPO%;%PYTHONPATH%"
cd /d "%MEMPALACE_REPO%"
python -m mempalace.mcp_server --palace "%PALACE_PATH%"
