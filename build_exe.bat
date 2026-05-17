@echo off
REM ============================================================================
REM  Translation Manager — Windows EXE build
REM
REM  1) Builds the React frontend (npm run build) → frontend/dist/
REM  2) Bundles main_eel.py + translation_manager package + frontend/dist into
REM     a single TranslationManager.exe using PyInstaller.
REM
REM  Requirements (one-time):
REM     pip install pyinstaller eel requests pillow
REM     cd frontend && npm install
REM
REM  Output: dist\TranslationManager.exe
REM ============================================================================

setlocal enableextensions

cd /d "%~dp0"

echo.
echo === [1/3]  Building React frontend (npm run build) ===
pushd frontend
call npm run build
if errorlevel 1 (
    echo.
    echo [build_exe] frontend build FAILED — aborting.
    popd
    exit /b 1
)
popd

if not exist "frontend\dist\index.html" (
    echo [build_exe] frontend\dist\index.html missing after npm run build — aborting.
    exit /b 1
)

echo.
echo === [2/3]  Cleaning previous PyInstaller output ===
if exist build      rmdir /s /q build
if exist dist       rmdir /s /q dist
if exist TranslationManager.spec del /q TranslationManager.spec

echo.
echo === [3/3]  Running PyInstaller ===
REM  --windowed         : no console window (GUI app)
REM  --onefile          : single self-extracting .exe
REM  --noconfirm        : don't prompt before overwriting
REM  --add-data SRC;DST : ship the built React app + games/news/updates JSON
REM  --collect-data eel : Eel ships its own eel.js — make sure it's bundled
REM  --collect-submodules eel : Eel uses dynamic imports under the hood
REM  --hidden-import bottle / gevent... : Eel's transport deps
REM
REM  NOTE: on Windows the --add-data separator is ";", not ":"
python -m PyInstaller ^
    --noconfirm ^
    --windowed ^
    --onefile ^
    --clean ^
    --name "TranslationManager" ^
    --icon "build_assets\app.ico" ^
    --add-data "frontend\dist;frontend/dist" ^
    --add-data "games.json;." ^
    --add-data "news.json;." ^
    --add-data "updates.json;." ^
    --add-data "translation_manager;translation_manager" ^
    --collect-data eel ^
    --collect-submodules eel ^
    --hidden-import bottle ^
    --hidden-import bottle_websocket ^
    --hidden-import gevent ^
    --hidden-import gevent.monkey ^
    --hidden-import gevent.queue ^
    --hidden-import geventwebsocket ^
    --hidden-import geventwebsocket.handler ^
    main_eel.py

if errorlevel 1 (
    echo.
    echo [build_exe] PyInstaller FAILED.
    exit /b 1
)

echo.
echo === BUILD SUCCESS ===
if exist "dist\TranslationManager.exe" (
    for %%I in ("dist\TranslationManager.exe") do echo Output: %%~fI   ^(%%~zI bytes^)
) else (
    echo [WARN] dist\TranslationManager.exe not found — check PyInstaller output above.
    exit /b 1
)

echo.
echo Next step:  compile installer.iss with Inno Setup 6
echo            ^("%%ProgramFiles(x86)%%\Inno Setup 6\ISCC.exe" installer.iss^)
echo.

endlocal
exit /b 0
