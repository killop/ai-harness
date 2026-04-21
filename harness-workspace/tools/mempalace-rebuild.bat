@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "WORKSPACE_ROOT=%%~fI"

if not "%MEMPALACE_PYTHON%"=="" (
  set "PYTHON_EXE=%MEMPALACE_PYTHON%"
) else (
  set "PYTHON_EXE=%WORKSPACE_ROOT%\mempalace-github-code\.venv\Scripts\python.exe"
)

if exist "%PYTHON_EXE%" goto run
where "%PYTHON_EXE%" >nul 2>&1
if not errorlevel 1 goto run

echo Missing Python executable "%PYTHON_EXE%".
echo Run mempalace-setup.bat first or set MEMPALACE_PYTHON.
exit /b 1

:run
echo Running: "%PYTHON_EXE%" "%SCRIPT_DIR%mempalace_tools.py" rebuild %*
"%PYTHON_EXE%" "%SCRIPT_DIR%mempalace_tools.py" rebuild %*
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo Exit code: %EXIT_CODE%
if /I "%MEMPALACE_NO_PAUSE%"=="1" exit /b %EXIT_CODE%
if defined CI exit /b %EXIT_CODE%
pause
exit /b %EXIT_CODE%
