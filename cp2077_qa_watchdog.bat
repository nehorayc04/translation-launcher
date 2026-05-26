@echo off
REM ===================================================================
REM cp2077_qa_watchdog.bat
REM Keeps the Cyberpunk 2077 Hebrew QA watchdog ("castle guard") running.
REM Auto-restarts it 30s after any exit/crash so the guard never sleeps.
REM
REM For boot persistence: Task Scheduler -> Create Task -> Trigger
REM "At log on" -> Action: Start this .bat.
REM ===================================================================
cd /d "%~dp0"
:loop
echo [%date% %time%] starting cp2077_qa_watchdog.py
python cp2077_qa_watchdog.py
echo [%date% %time%] watchdog exited (code %errorlevel%) - restarting in 30s...
timeout /t 30 /nobreak >nul
goto loop
