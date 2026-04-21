@echo off
setlocal

set "SCRIPT_DIR=%~dp0"

if not "%MEMPALACE_SETUP_PYTHON%"=="" (
  set "PYTHON_EXE=%MEMPALACE_SETUP_PYTHON%"
) else (
  if not "%MEMPALACE_PYTHON%"=="" (
    set "PYTHON_EXE=%MEMPALACE_PYTHON%"
  ) else (
    set "PYTHON_EXE=python"
  )
)

if exist "%PYTHON_EXE%" goto run
where "%PYTHON_EXE%" >nul 2>&1
if not errorlevel 1 goto run

where py >nul 2>&1
if not errorlevel 1 (
  py -3 "%SCRIPT_DIR%mempalace_tools.py" setup %*
  exit /b %ERRORLEVEL%
)

echo Missing Python executable "%PYTHON_EXE%".
echo Set MEMPALACE_SETUP_PYTHON or install Python first.
exit /b 1

:run
echo Running: "%PYTHON_EXE%" "%SCRIPT_DIR%mempalace_tools.py" setup %*
"%PYTHON_EXE%" "%SCRIPT_DIR%mempalace_tools.py" setup %*
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo Exit code: %EXIT_CODE%
if /I "%MEMPALACE_NO_PAUSE%"=="1" exit /b %EXIT_CODE%
if defined CI exit /b %EXIT_CODE%
pause
exit /b %EXIT_CODE%
