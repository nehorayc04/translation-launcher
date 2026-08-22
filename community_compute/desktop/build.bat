@echo off
REM Build the Community Compute desktop worker EXE.
REM Run from this folder with the repo .venv python on PATH, or double-click.
setlocal
cd /d "%~dp0"
set PY="%~dp0..\..\.venv\Scripts\python.exe"
%PY% -m PyInstaller --noconfirm --clean CommunityCompute.spec
echo.
echo Output: %~dp0dist\CommunityCompute.exe
endlocal
