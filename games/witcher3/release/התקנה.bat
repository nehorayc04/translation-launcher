@echo off
rem The Witcher 3 - Hebrew translation. Double-click this file to open the installer.
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>&1 && ( py install_console.py & goto done )
where python >nul 2>&1 && ( python install_console.py & goto done )
echo.
echo ============================================================
echo   Python 3.9+ is required (free): https://python.org
echo   During setup, tick "Add python.exe to PATH".
echo   Then double-click this file again.
echo ============================================================
echo.
pause
:done
