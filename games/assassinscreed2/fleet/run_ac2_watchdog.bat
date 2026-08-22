@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ac2_watchdog.ps1" >> C:\tmp\ac2_watchdog_run.log 2>&1
