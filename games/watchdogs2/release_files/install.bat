@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 install.py 2>nul || python install.py
echo.
pause
