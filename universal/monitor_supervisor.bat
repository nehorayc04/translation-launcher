@echo off
REM ===================================================================
REM monitor_supervisor.bat
REM Keeps `python -m progress_monitor --adapter audit --no-tui` alive.
REM
REM Why this exists: the monitor was launched once from a terminal that
REM later closed (or crashed silently after ~36h), leaving the website
REM's quality-control row stuck on a stale processed value for hours
REM while the audit kept making real progress. There was no auto-restart
REM because no supervisor was watching it.
REM
REM Restarts the monitor 30s after any exit (clean or crash). Pushes
REM stdout+stderr into monitor_audit.err.log so file persists across
REM the loop.
REM
REM Spawn this once at boot (or from start_audit.bat) with:
REM   start "" /b cmd /c "monitor_supervisor.bat"
REM ===================================================================
cd /d "%~dp0"

REM Singleton guard. If another monitor_supervisor.bat is already running
REM (start_audit.bat already spawned one, OR the user double-clicked this
REM bat directly while a stack was up) bail BEFORE starting the loop so
REM we don't end up with parallel monitors racing on /api/admin/progress.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_check_single.ps1" monitor_supervisor
if errorlevel 1 (
  echo [%date% %time%] [mon-sup] another instance already running - exiting>> monitor_audit.err.log
  exit /b 0
)

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

set PY="%~dp0..\.venv\Scripts\python.exe"
if not exist %PY% set PY=python.exe

:loop
echo [%date% %time%] [mon-sup] launching progress_monitor --adapter audit
echo [%date% %time%] [mon-sup] launching progress_monitor --adapter audit>> monitor_audit.err.log
%PY% -m progress_monitor --adapter audit --no-tui >> monitor_audit.err.log 2>&1
set EC=%errorlevel%
echo [%date% %time%] [mon-sup] monitor exited code=%EC% - restarting in 30s...
echo [%date% %time%] [mon-sup] monitor exited code=%EC% - restarting in 30s...>> monitor_audit.err.log
timeout /t 30 /nobreak >nul
goto loop
