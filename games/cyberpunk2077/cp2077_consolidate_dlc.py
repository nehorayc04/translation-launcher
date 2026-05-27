"""
cp2077_consolidate_dlc.py
=========================
Consolidates the serialized Phantom Liberty (ep1 DLC) localization files into
a single JSON — dlc_ep1_text.json — so cp2077_status_report.py can scan the
DLC the same way it scans the base game.

dlc_ep1_text.json shape mirrors localization_export.json:
    { "<section key>": [ {entry}, ... ], ... }
section keys are prefixed `ep1/` (e.g. `ep1/onscreens/onscreens_final.json`,
`ep1/subtitles/quest/q301/q301_01_...json`).

PREREQUISITE — the DLC localization must first be extracted + serialized into
C:\\tmp\\dlc_scan (read-only, one-time). Rebuild it with WolvenKit.CLI:

    WKIT = C:\\Users\\nc528\\AppData\\Local\\Programs\\WolvenKit-CLI\\WolvenKit.CLI.exe
    EP1  = ...\\Cyberpunk 2077\\archive\\pc\\ep1\\lang_en_text.archive

    %WKIT% extract  %EP1%  -o C:\\tmp\\dlc_scan\\raw
    %WKIT% convert serialize C:\\tmp\\dlc_scan\\raw\\ep1\\localization\\en-us\\onscreens -o C:\\tmp\\dlc_scan\\txt
    # then, for each subtitles top-folder <F> in
    #   media open_world overlays_quest overlay_media overlay_open_world quest
    %WKIT% convert serialize C:\\tmp\\dlc_scan\\raw\\ep1\\localization\\en-us\\subtitles\\<F> -o C:\\tmp\\dlc_scan\\txt_<F>

subtitles/subtitles.json is the subtitle-file INDEX (localizationPersistence-
SubtitleMapEntry — depot paths, no displayed text) and is intentionally skipped.
"""
from __future__ import annotations

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCAN    = r"C:\tmp\dlc_scan"
RAW_SUB = os.path.join(SCAN, "raw", "ep1", "localization", "en-us", "subtitles")
RES     = r"C:\Users\nc528\סקריפטים\תרגום משחקים\תרגום_משחקים\source\resources"
OUT     = os.path.join(RES, "dlc_ep1_text.json")

SUB_FOLDERS = ["media", "open_world", "overlays_quest",
               "overlay_media", "overlay_open_world", "quest"]


def entries_of(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["Data"]["RootChunk"]["root"]["Data"]["entries"]


def main() -> int:
    if not os.path.isdir(SCAN):
        sys.exit(f"FATAL: {SCAN} not found — extract+serialize the DLC first "
                 f"(see the prerequisite block in this file's docstring).")

    result: dict[str, list] = {}

    # ── onscreens (2 files) ─────────────────────────────────────────────────
    for fn in ("onscreens.json", "onscreens_final.json"):
        p = os.path.join(SCAN, "txt", fn + ".json")
        if os.path.exists(p):
            key = f"ep1/onscreens/{fn}"
            result[key] = entries_of(p)
            print(f"  {key}: {len(result[key]):,} entries")

    # ── basename -> [relpath...] from the raw subtitles tree ────────────────
    # Lets us restore each flattened serialized file to its true ep1 path.
    basemap: dict[str, list[str]] = {}
    for root, _, files in os.walk(RAW_SUB):
        for f in files:
            if f.endswith(".json"):
                rel = os.path.relpath(os.path.join(root, f), RAW_SUB).replace(os.sep, "/")
                basemap.setdefault(f, []).append(rel)

    # ── subtitles, per top-folder ───────────────────────────────────────────
    sub_files = 0
    for folder in SUB_FOLDERS:
        txtdir = os.path.join(SCAN, f"txt_{folder}")
        if not os.path.isdir(txtdir):
            print(f"  [skip] {txtdir} missing")
            continue
        n = 0
        for fn in sorted(os.listdir(txtdir)):
            if not fn.endswith(".json.json"):
                continue
            base = fn[:-5]                       # "<name>.json.json" -> "<name>.json"
            cands = [r for r in basemap.get(base, []) if r.split("/")[0] == folder]
            rel = cands[0] if cands else f"{folder}/{base}"
            result[f"ep1/subtitles/{rel}"] = entries_of(os.path.join(txtdir, fn))
            n += 1
        sub_files += n
        print(f"  ep1/subtitles/{folder}: {n} files")

    os.makedirs(RES, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print(f"\n[OK] {len(result):,} sections "
          f"({sub_files} subtitle files + 2 onscreens) -> {OUT}")
    print(f"     {os.path.getsize(OUT):,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
