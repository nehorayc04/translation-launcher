"""
verify_18_fixes_in_archive.py
==============================
Targeted post-bake verification: extract ONLY the 6 sections that the
manual fix pass changed, then confirm each of the 18 patched
(section, primaryKey) entries has the expected Hebrew text in the baked
CR2W (no English / Arabic-skeleton residue).

Much faster than re-running the full deep audit: ~30-60 seconds vs ~3 h.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPTS_DIR = r"C:\Users\Nehoray_Cohen\Projects\Game translator"
GAME        = os.path.join(SCRIPTS_DIR, "Cyberpunk 2077")
MOD_MAIN    = os.path.join(GAME, "archive", "pc", "mod", "z_hebrew_translation.archive")
CLI         = r"C:\Users\Nehoray_Cohen\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
TRANSLATED  = os.path.join(SCRIPTS_DIR, "תרגום_משחקים", "source", "resources",
                            "localization_translated.json")

# (section_key, primaryKey, must-contain Hebrew substring — proves the fix landed)
EXPECTED = [
    # A — manual translations (apply_deep_audit_translations.py)
    ("onscreens/onscreens.json",       "77919", "סכנות מודגשות"),
    ("onscreens/onscreens.json",       "87898", "פותח את מצב"),
    ("onscreens/onscreens.json",       "95358", "חתימת GPS"),
    ("onscreens/onscreens_final.json", "95358", "חתימת GPS"),
    ("subtitles/quest/mq028/mq028_02_park.json", "1975313822573043712", "להישאר בשקט"),
    # B — leak fixes (apply_leak_fixes.py)
    ("onscreens/onscreens.json",       "6269",  "הבג בא לב של החיה"),
    ("onscreens/onscreens_final.json", "6269",  "הבג בא לב של החיה"),
    ("onscreens/onscreens.json",       "6269",  "לקואורדינטות הללו"),
    ("onscreens/onscreens_final.json", "6269",  "לקואורדינטות הללו"),
    ("onscreens/onscreens.json",       "11534", "אני הולך לחסל את כולם"),
    ("onscreens/onscreens_final.json", "11534", "אני הולך לחסל את כולם"),
    ("onscreens/onscreens.json",       "11534", "יא כלבה"),
    ("onscreens/onscreens_final.json", "11534", "יא כלבה"),
    ("onscreens/onscreens.json",       "82710", "התברר שהמרקם"),
    ("onscreens/onscreens_final.json", "82710", "התברר שהמרקם"),
    ("onscreens/onscreens_final.json", "11521", "אותם תולעים"),
    ("onscreens/onscreens_final.json", "83878", "אותם בייקרס"),
    ("onscreens/onscreens_final.json", "84326", "אני אחשוב על זה"),
    ("onscreens/onscreens_final.json", "84326", "נושא: שיני את דעתך"),
    ("onscreens/onscreens_final.json", "86817", "החדשים האלה"),
    ("onscreens/onscreens_final.json", "86817", "נושא: איך פאנט"),
    ("subtitles/open_world/voicesets/gang_scv_m_11_rus_40_mt.json",
        "1898039435881734148", "ואשלח אותך לירח"),
    ("subtitles/open_world/voicesets/gang_vdb_f_03_car_30_mt.json",
        "1949022741939134468", "אני אהרוג אותך"),
    ("subtitles/quest/q103/q103_07_ghost_town_drive.json",
        "1665069818135048192", "המטוסים הענקיים האלה"),
]

# Anti-checks: these strings MUST NOT appear in the baked entry — old English.
NEGATIVE = [
    ("onscreens/onscreens.json",       "6269",  "heart של החיה"),
    ("onscreens/onscreens_final.json", "6269",  "heart של החיה"),
    ("onscreens/onscreens.json",       "6269",  "these coordinates"),
    ("onscreens/onscreens_final.json", "6269",  "these coordinates"),
    ("onscreens/onscreens.json",       "11534", "going to wipe em all"),
    ("onscreens/onscreens_final.json", "11534", "going to wipe em all"),
    ("onscreens/onscreens.json",       "11534", "שליBitch"),
    ("onscreens/onscreens_final.json", "11534", "שליBitch"),
    ("onscreens/onscreens.json",       "82710", "Turned out, the All Foods"),
    ("onscreens/onscreens_final.json", "82710", "Turned out, the All Foods"),
    ("onscreens/onscreens_final.json", "11521", "בשביל them תולעים"),
    ("onscreens/onscreens_final.json", "83878", "עם them בייקרס"),
    ("onscreens/onscreens_final.json", "84326", "A'll think about it"),
    ("onscreens/onscreens_final.json", "84326", "เรื่อง:"),
    ("onscreens/onscreens_final.json", "86817", "those new Arasaka"),
    ("onscreens/onscreens_final.json", "86817", "เรื่อง:"),
    ("subtitles/open_world/voicesets/gang_scv_m_11_rus_40_mt.json",
        "1898039435881734148", "lanz you"),
    ("subtitles/open_world/voicesets/gang_vdb_f_03_car_30_mt.json",
        "1949022741939134468", "א öld you"),
    ("subtitles/quest/q103/q103_07_ghost_town_drive.json",
        "1665069818135048192", "them huge transporters"),
]

# Files to extract — derived from sections.
FILES_TO_BAKE_PATHS = sorted({sec for sec, _, _ in EXPECTED})


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run_cli(args, timeout=300) -> tuple[bool, str]:
    try:
        r = subprocess.run([CLI] + args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return False, f"EXC: {e}"


def extract_and_serialize(work: Path) -> dict[str, list[dict]]:
    """Extract the 6 target files from the deployed archive, serialize each,
    return {section_key: entries_list}.
    """
    raw  = work / "raw"
    jout = work / "json"
    raw.mkdir(parents=True, exist_ok=True)
    jout.mkdir(parents=True, exist_ok=True)

    # Build wildcard patterns from the 6 section paths' BASENAMES — WolvenKit
    # only supports name-substring globs.
    basenames = sorted({Path(sec).name for sec in FILES_TO_BAKE_PATHS})
    for bn in basenames:
        log(f"  extract -w '*{bn}*'")
        ok, msg = run_cli(["extract", MOD_MAIN, "-o", str(raw), "-w", f"*{bn}*"])
        if not ok:
            log(f"    extract failed: {msg[-200:]}")

    sections: dict[str, list[dict]] = {}
    for sec in FILES_TO_BAKE_PATHS:
        cr2w = raw / "base" / "localization" / "ar-ar" / Path(sec)
        if not cr2w.exists():
            log(f"  [missing] {cr2w}")
            continue
        out_dir = jout / Path(sec).parent
        out_dir.mkdir(parents=True, exist_ok=True)
        ok, msg = run_cli(["convert", "serialize", str(cr2w), "-o", str(out_dir)])
        if not ok:
            log(f"  [serialize failed] {sec}: {msg[-200:]}")
            continue
        serialized = out_dir / (cr2w.name + ".json")
        if not serialized.exists():
            log(f"  [serialize empty] expected {serialized}")
            continue
        with open(serialized, "r", encoding="utf-8") as f:
            data = json.load(f)
        sections[sec] = data["Data"]["RootChunk"]["root"]["Data"]["entries"]
    return sections


def main() -> int:
    log("=" * 70)
    log(f"verify against {MOD_MAIN}")
    log(f"  archive mtime: "
        f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(MOD_MAIN)))}")
    log(f"  archive size:  {os.path.getsize(MOD_MAIN):,} bytes")
    log("=" * 70)

    work = Path(tempfile.mkdtemp(prefix="cp2077_verify_"))
    log(f"workdir: {work}")
    try:
        baked = extract_and_serialize(work)
        log(f"serialized {len(baked)} / {len(FILES_TO_BAKE_PATHS)} sections")

        def find_entry(sec, pk):
            for e in baked.get(sec, []):
                if str(e.get("primaryKey") or e.get("stringId")) == pk:
                    return e
            return None

        # POSITIVE checks
        passed_pos = 0
        for sec, pk, needle in EXPECTED:
            e = find_entry(sec, pk)
            if e is None:
                log(f"  [POS MISS] {sec} pk={pk} → entry not in baked CR2W")
                continue
            fv = e.get("femaleVariant", "") or ""
            if needle in fv:
                passed_pos += 1
            else:
                log(f"  [POS FAIL] {sec} pk={pk}: needle {needle!r} NOT in fv")
                log(f"             actual fv (first 200): {fv[:200]!r}")

        # NEGATIVE checks
        passed_neg = 0
        for sec, pk, bad in NEGATIVE:
            e = find_entry(sec, pk)
            if e is None:
                log(f"  [NEG MISS] {sec} pk={pk} → entry not in baked CR2W")
                continue
            fv = e.get("femaleVariant", "") or ""
            if bad in fv:
                log(f"  [NEG FAIL] {sec} pk={pk}: forbidden {bad!r} STILL PRESENT in fv")
            else:
                passed_neg += 1

        log("=" * 70)
        log(f"POSITIVE checks: {passed_pos}/{len(EXPECTED)} passed")
        log(f"NEGATIVE checks: {passed_neg}/{len(NEGATIVE)} passed (forbidden English absent)")
        log("=" * 70)
        return 0 if (passed_pos == len(EXPECTED) and passed_neg == len(NEGATIVE)) else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
