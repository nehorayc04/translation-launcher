@echo off
REM Pull the fleet's newest lines, rebuild the whole LML override and redeploy it.
REM Runs unattended on a 30-minute task so the installed mod is never more than half an
REM hour behind the fleet, even if nobody is watching.
REM
REM MUST use the repo .venv python: rdr2_rtl needs python-bidi, and the base interpreter
REM fails the import with a bare ModuleNotFoundError that reads like a broken build.
set REPO=C:\Users\Nehoray_Cohen\Projects\Game translator
set LOG=C:\tmp\rdr2_refresh.log
echo ==== %DATE% %TIME% ==== >> "%LOG%"
"C:\Program Files\Git\bin\bash.exe" -lc "cd '/c/Users/Nehoray_Cohen/Projects/Game translator' && bash games/rdr2/fleet/pull_missing.sh" >> "%LOG%" 2>&1
"%REPO%\.venv\Scripts\python.exe" "%REPO%\games\rdr2\work\build_full.py" --deploy >> "%LOG%" 2>&1
echo ---- done %TIME% >> "%LOG%"
