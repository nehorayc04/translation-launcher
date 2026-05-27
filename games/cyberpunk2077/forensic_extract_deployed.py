"""Pull the actually-deployed onscreens.json out of z_hebrew_translation.archive
and print the Hebrew text for the 3 UI bug PKs (361, 1539, 80643).

If the strings match the latest source localization_translated.json the
fix made it into the archive — the issue is elsewhere (mod load order,
cache, save state). If they're the OLD text we have a stale-cache bug
in the rebuild pipeline.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace", write_through=True)

CLI       = Path(r"C:\Users\nc528\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe")
ARCHIVE   = Path(r"C:\Users\nc528\סקריפטים\תרגום משחקים\Cyberpunk 2077\archive\pc\mod\z_hebrew_translation.archive")
WORK      = Path(r"C:\Users\nc528\AppData\Local\Temp\forensic_deploy")
SRC_JSON  = Path(r"c:\Users\nc528\סקריפטים\תרגום משחקים\תרגום_משחקים\source\resources\localization_translated.json")

PKS = {361: "Enter Breach View", 1539: "LEVEL", 80643: "Wait {value} h"}


def run(args, timeout=600):
    r = subprocess.run([str(CLI)] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode == 0, (r.stdout or "") + (r.stderr or "")


def find_pk(rows, pk):
    for e in rows:
        if isinstance(e, dict) and str(e.get("primaryKey")) == str(pk):
            return e.get("femaleVariant"), e.get("maleVariant")
    return None, None


def main():
    for p in (CLI, ARCHIVE, SRC_JSON):
        if not p.exists():
            sys.exit(f"missing: {p}")

    if WORK.exists():
        shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)
    extract_dir = WORK / "raw"
    text_dir    = WORK / "text"
    extract_dir.mkdir(); text_dir.mkdir()

    print(f"[*] Extracting onscreens CR2W from {ARCHIVE.name} ({ARCHIVE.stat().st_size:,} bytes)")
    ok, out = run(["extract", str(ARCHIVE), "-o", str(extract_dir),
                   "-w", "*onscreens*"], timeout=120)
    if not ok:
        print(out[-800:])
        sys.exit("extract failed")
    cr2w_files = sorted(extract_dir.rglob("onscreens*.json"))
    if not cr2w_files:
        sys.exit(f"no onscreens*.json found under {extract_dir}")
    print(f"[*] extracted {len(cr2w_files)} CR2W file(s):")
    for f in cr2w_files:
        print(f"    {f.relative_to(extract_dir)}  ({f.stat().st_size:,} bytes)")

    print()
    print(f"[*] Serializing CR2W -> text JSON")
    for f in cr2w_files:
        ok, out = run(["convert", "serialize", str(f), "-o", str(text_dir)],
                      timeout=180)
        if not ok:
            print(out[-800:])
            sys.exit(f"serialize failed for {f.name}")
    txt_files = sorted(text_dir.glob("onscreens*.json"))
    print(f"[*] serialized {len(txt_files)} text JSON(s)")
    for f in txt_files:
        print(f"    {f.name}  ({f.stat().st_size:,} bytes)")

    # WolvenKit text JSON structure: {"Header":..., "Data":{"RootChunk":{...,
    #   "root":[{"Chunk":{"primaryKey":..., "femaleVariant":{...}, ...}}]}}}.
    # The exact path varies a bit by WolvenKit version — walk for primaryKey.
    print()
    print(f"[*] Loading source {SRC_JSON.name} for comparison")
    with open(SRC_JSON, "r", encoding="utf-8") as f:
        src = json.load(f)

    for txt in txt_files:
        print(f"\n{'='*70}")
        print(f"FILE INSIDE DEPLOYED ARCHIVE: {txt.name}")
        print('='*70)
        with open(txt, "r", encoding="utf-8") as f:
            doc = json.load(f)

        # Walk for the root entries list. CR2W onscreens carries entries
        # in Data.RootChunk.root (list of CR2W chunks, each a dict with
        # primaryKey/femaleVariant/maleVariant).
        # Be defensive — different WK versions wrap it differently.
        def walk(obj, key="primaryKey"):
            stack = [obj]
            while stack:
                cur = stack.pop()
                if isinstance(cur, dict):
                    if key in cur and isinstance(cur.get(key), int):
                        yield cur
                    for v in cur.values():
                        stack.append(v)
                elif isinstance(cur, list):
                    stack.extend(cur)
        entries = list(walk(doc))
        print(f"  {len(entries):,} entries parsed from CR2W text JSON")

        # Source-side equivalent
        src_section = "onscreens/" + txt.name.replace(".json.json", ".json")
        src_rows = src.get(src_section, [])
        print(f"  (source has {len(src_rows):,} entries in {src_section})")

        print()
        for pk, label in PKS.items():
            archive_e = next((e for e in entries if e.get("primaryKey") == pk), None)
            src_fv, src_mv = find_pk(src_rows, pk)

            def get_text(field):
                """Pull the actual text out of WolvenKit's wrapped field shape
                (femaleVariant is usually {"Value":"...","HandleRefId":...})."""
                if archive_e is None:
                    return None
                v = archive_e.get(field)
                if isinstance(v, dict):
                    return v.get("Value") or v.get("value") or v.get("text")
                return v

            arc_fv = get_text("femaleVariant")
            arc_mv = get_text("maleVariant")

            status = "MATCH ✓" if (arc_fv == src_fv) else "MISMATCH ✗"
            print(f"  pk={pk}  ({label})  [{status}]")
            print(f"    in deployed archive  femaleVariant: {arc_fv!r}")
            print(f"    in source JSON       femaleVariant: {src_fv!r}")
            if arc_mv or src_mv:
                print(f"    in deployed archive  maleVariant:   {arc_mv!r}")
                print(f"    in source JSON       maleVariant:   {src_mv!r}")


if __name__ == "__main__":
    main()
