@echo off
REM ==============================================================================
REM Horse Havoc - 1-Click Windows Task Scheduler Registration (Daily at 12:00 PM)
REM ==============================================================================
setlocal EnableDelayedExpansion

cd /d "%~dp0"
set PROJECT_DIR=%~dp0
set SCRIPT_PATH=%PROJECT_DIR%run_pipeline.py
set TASK_NAME=HorseHavoc_Daily_Pipeline
set RUN_TIME=12:00

echo ======================================================================
echo  [HORSE HAVOC] WINDOWS TASK SCHEDULER SETUP (1-CLICK)
echo ======================================================================
echo  * Task Name   : %TASK_NAME%
echo  * Daily Time  : %RUN_TIME%
echo  * Target Script: %SCRIPT_PATH%
echo ----------------------------------------------------------------------

for /f "delims=" %%I in ('where python.exe') do (
    set PYTHON_EXE=%%I
    goto :found_python
)

:found_python
if "%PYTHON_EXE%"=="" set PYTHON_EXE=python.exe

schtasks /Create /SC DAILY /TN "%TASK_NAME%" /TR "\"%PYTHON_EXE%\" \"%SCRIPT_PATH%\"" /ST %RUN_TIME% /F

if %ERRORLEVEL% equ 0 (
    echo.
    echo  SUCCESS: Task registered to run automatically every day at %RUN_TIME%!
    echo  To test task immediately: schtasks /Run /TN "%TASK_NAME%"
) else (
    echo.
    echo  [!] Error creating scheduled task. Try right-clicking and 'Run as administrator'.
)

echo ======================================================================
pause

