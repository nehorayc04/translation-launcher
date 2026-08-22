@echo off
REM Wrapper for Windows Task Scheduler -> runs the git-bash fleet heal+report every 10 min.
"C:\Program Files\Git\bin\bash.exe" -lc "'/c/Users/Nehoray_Cohen/Projects/Game translator/games/cyberpunk2077/fleet_report_once.sh'"
