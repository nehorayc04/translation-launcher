@echo off
REM Runs deploy.py elevated and tees everything to a log the caller can read.
REM %* is forwarded to deploy.py (e.g. --proof, --revert).
set PY=c:\Users\Nehoray_Cohen\Projects\Game translator\.venv\Scripts\python.exe
set HERE=%~dp0
cd /d "%HERE%"
"%PY%" -u deploy.py %* > "%HERE%elevated.log" 2>&1
echo EXITCODE=%ERRORLEVEL% >> "%HERE%elevated.log"
