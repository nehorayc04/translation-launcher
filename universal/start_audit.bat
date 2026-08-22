@echo off
REM ===================================================================
REM start_audit.bat
REM Two-layer self-heal for continuous_audit_loop.py:
REM
REM   1. Supervisor LOOP (this .bat) — relaunches the script 30s after
REM      any exit, so a clean crash is caught.
REM
REM   2. Hang watchdog (PowerShell, run alongside) — kills the script
REM      if the checkpoint file hasn't been written for more than
REM      HANG_SECONDS (default 360 s ≈ 3 batches worth of work). That
REM      forces an exit, which the supervisor catches above.
REM
REM      The script's own per-row retry budget is 3 × (90s timeout +
REM      30s sleep) = up to 6 min for a single stuck row, and a chain
REM      of stuck rows can multiply that — without a wall-clock
REM      watchdog, a bad LM Studio mood can stall the audit for hours.
REM
REM Run interactively (Ctrl+C stops both loops), OR add as a Scheduled
REM Task with trigger "At log on" for boot persistence.
REM ===================================================================
cd /d "%~dp0"

REM Singleton guard. A second start_audit.bat would spawn its own watchdog
REM + monitor_supervisor children, race the audit lock, and double-push
REM to the API. Bail BEFORE doing anything if another instance exists.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_check_single.ps1" start_audit
if errorlevel 1 (
  echo [%date% %time%] [supervisor] another instance already running - exiting>> audit.log
  exit /b 0
)

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

REM Watchdog hang threshold. The default 360s was tuned for small batches;
REM with --batch-size 20 a NORMAL batch is ~300s and the checkpoint only
REM saves at batch end, so one slow row would push past 360s and the
REM watchdog would kill a healthy-but-slow batch BEFORE the script's own
REM per-row skip (3 x 90s timeout + 30s backoff = 330s) could recover it.
REM 900s gives the in-script self-heal room to skip a stuck row and finish
REM the batch; only a TRUE total hang (no checkpoint for 15 min) is killed.
set AUDIT_HANG_SECONDS=900

REM Pick the project's .venv if it exists, fall back to system python.
set PY="%~dp0..\.venv\Scripts\python.exe"
if not exist %PY% set PY=python.exe

REM Spawn the hang watchdog ONCE (it loops internally). Detached so it
REM survives across audit restarts.
start "" /b powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0audit_hang_watchdog.ps1"

REM Spawn the monitor supervisor ONCE so the website's quality-control
REM row stays fresh. It loops internally; without it the monitor was
REM a single-shot launch that died after ~36 h and left the API stale.
start "" /b cmd /c "%~dp0monitor_supervisor.bat"

:loop
echo [%date% %time%] [supervisor] launching continuous_audit_loop.py
echo [%date% %time%] [supervisor] launching continuous_audit_loop.py>> audit.log
REM Tee stdout+stderr into audit.log so the file captures the full
REM per-batch progress + any traceback. The console window is quiet
REM during runs — tail audit.log to watch progress live:
REM   Get-Content audit.log -Tail 20 -Wait
%PY% continuous_audit_loop.py --batch-size 8 >> audit.log 2>&1
set EC=%errorlevel%
echo [%date% %time%] [supervisor] audit exited code=%EC% - restarting in 30s...
echo [%date% %time%] [supervisor] audit exited code=%EC% - restarting in 30s...>> audit.log
timeout /t 30 /nobreak >nul
goto loop
