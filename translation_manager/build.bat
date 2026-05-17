@echo off
REM ── Build TranslationManager.exe (single file, no console) ──
REM Place an icon.ico next to this file before running, or remove --icon.

cd /d "%~dp0"

pyinstaller ^
    --onefile ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --name "TranslationManager" ^
    --icon "icon.ico" ^
    --collect-all customtkinter ^
    --paths ".." ^
    run.py

echo.
echo === Build complete ===
echo Output: dist\TranslationManager.exe
pause
