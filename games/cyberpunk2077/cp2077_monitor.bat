@echo off
chcp 65001 >NUL
title CP2077 progress monitor
cd /d "%~dp0"

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONPATH=%~dp0..\..\universal;%PYTHONPATH%

python -m progress_monitor --adapter cp2077 --tui

echo.
echo ------------------------------------------------------------
echo Monitor exited with code %ERRORLEVEL%.
echo ------------------------------------------------------------
pause
