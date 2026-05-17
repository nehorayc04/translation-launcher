@echo off
title CP2077 progress monitor
cd /d "%~dp0"

echo ============================================================
echo  Cyberpunk 2077 progress monitor
echo  Pushes a snapshot every 15 minutes to:
echo    https://hebrew-translation-hub.vercel.app/api/admin/progress
echo  Close this window or press Ctrl+C to stop.
echo ============================================================
echo.

python -m progress_monitor --adapter cp2077

echo.
echo ------------------------------------------------------------
echo Monitor exited with code %ERRORLEVEL%.
echo ------------------------------------------------------------
pause
