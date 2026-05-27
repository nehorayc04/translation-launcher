@echo off
REM ============================================================================
REM  cleanup_subtitles.bat — finish the Hebrew subtitle translation.
REM
REM  Run this once (overnight — it's long). It:
REM    1. Translates every still-untranslated subtitle line via LM Studio.
REM    2. Re-bakes the affected subtitle CR2W files and deploys the archive
REM       to the game folder the launcher actually uses.
REM
REM  Prerequisite: LM Studio running with gemma-2-27b loaded, local server on.
REM  Cyberpunk 2077 must be CLOSED (the deploy archive gets overwritten).
REM
REM  cleanup_queue.json must already exist — produced by
REM  build_subtitle_cleanup_queue.py (3,246 entries as of the last build).
REM ============================================================================

setlocal
cd /d "%~dp0"

if not exist "cleanup_queue.json" (
    echo [cleanup] cleanup_queue.json missing — run build_subtitle_cleanup_queue.py first.
    exit /b 1
)
if not exist "subtitle_cleanup_sections.txt" (
    echo [cleanup] subtitle_cleanup_sections.txt missing — run build_subtitle_cleanup_queue.py first.
    exit /b 1
)

echo.
echo === [1/2] Translating untranslated subtitle lines (LM Studio, ~4-5 hours) ===
python translate_cleanup_all.py --no-rebuild
if errorlevel 1 (
    echo [cleanup] translation step FAILED — aborting before re-bake.
    exit /b 1
)

echo.
echo === [2/2] Re-baking + deploying affected subtitle files (~2 hours) ===
python rebuild_subtitles_and_pack.py --sections-file subtitle_cleanup_sections.txt
if errorlevel 1 (
    echo [cleanup] re-bake step FAILED.
    exit /b 1
)

echo.
echo === CLEANUP COMPLETE — subtitles fully translated + deployed ===
endlocal
