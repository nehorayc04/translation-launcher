#!/usr/bin/env bash
# Launcher re-release v1.1.0 (in place, new BUILD_ID) carrying the _parse_version
# fix so existing installs see the CP2077 mod v1.0.2 update.
cd "c:/Users/Nehoray_Cohen/Projects/Game translator" || exit 1
ISCC="C:/Users/Nehoray_Cohen/AppData/Local/Programs/Inno Setup 6/ISCC.exe"

echo "[rel] === [1/3] build_exe.bat (frontend + BUILD_ID + PyInstaller) $(date +%H:%M:%S) ==="
cmd //c build_exe.bat
if [ ! -f "dist/TranslationManager/TranslationManager.exe" ]; then
  echo "[rel] FATAL: TranslationManager.exe was not produced — aborting."
  exit 1
fi
echo "[rel] exe OK: $(stat -c%s 'dist/TranslationManager/TranslationManager.exe') bytes"

echo "[rel] === [2/3] Inno Setup compile installer.iss $(date +%H:%M:%S) ==="
"$ISCC" installer.iss
if [ ! -f "Output/TranslationManager-Setup-1.1.0.exe" ]; then
  echo "[rel] FATAL: installer was not produced — aborting."
  exit 1
fi
echo "[rel] installer OK: $(stat -c%s 'Output/TranslationManager-Setup-1.1.0.exe') bytes"

echo "[rel] === [3/3] publish_release.py 1.1.0 (GitHub + Supabase) $(date +%H:%M:%S) ==="
python publish_release.py 1.1.0
echo "[rel] === DONE $(date +%H:%M:%S) ==="
