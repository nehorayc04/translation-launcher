@echo off
REM ===================================================================
REM start_audit.bat
REM Keeps continuous_audit_loop.py running. The audit can exit for many
REM reasons — LM Studio cold reload, transient HTTP 500, OS sleep/wake,
REM occasional power blip — and previously a single exit left the
REM website's quality-control row stale for hours until someone noticed.
REM This supervisor restarts the audit 30 s after any exit so the live
REM feed self-heals; every restart leaves a line in audit.log alongside
REM whatever traceback the script's own crash trap recorded, so future
REM crashes are diagnosable from the file alone.
REM
REM Run interactively (Ctrl+C in this window stops the loop), OR add as
REM a Scheduled Task with trigger "At log on" for boot persistence.
REM ===================================================================
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

REM Pick the project's .venv if it exists, fall back to system python.
set PY="%~dp0..\.venv\Scripts\python.exe"
if not exist %PY% set PY=python.exe

:loop
echo [%date% %time%] [supervisor] launching continuous_audit_loop.py
echo [%date% %time%] [supervisor] launching continuous_audit_loop.py>> audit.log
REM Tee the script's stdout+stderr into audit.log so the file captures
REM the full per-batch progress + any traceback, not just the script's
REM own _log() calls. Even when the script stalls without crashing, the
REM file shows the last batch the script was working on.
%PY% continuous_audit_loop.py >> audit.log 2>&1
set EC=%errorlevel%
echo [%date% %time%] [supervisor] audit exited code=%EC% - restarting in 30s...
echo [%date% %time%] [supervisor] audit exited code=%EC% - restarting in 30s...>> audit.log
timeout /t 30 /nobreak >nul
goto loop
