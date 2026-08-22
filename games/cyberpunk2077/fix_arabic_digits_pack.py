"""
fix_arabic_digits_pack.py
=========================
Root-cause fix for the "KM with no number" bug (and likely the empty
settings-button bug too).

DIAGNOSIS
---------
When Cyberpunk 2077 runs in Arabic-language mode, its numeric formatter
emits digits as Arabic-Indic codepoints U+0660-U+0669 (٠١٢٣٤٥٦٧٨٩),
NOT as Latin ASCII 0-9. Our Heebo-based replacement font (deployed at
.../ara_es_nawar/araesnawar-regular.fnt) has glyphs for Latin 0-9 but
NONE for U+0660-U+0669 or U+06F0-U+06F9. So the digits render invisible
while their unit suffix ("KM", "%") renders fine.

FIX
---
Add `cmap` entries mapping U+0660-U+0669 and U+06F0-U+06F9 to the EXISTING
Latin 0-9 glyph IDs in the font. No new glyphs are designed — the engine
asks for ٠ and gets the glyph for 0. Zero quality loss.

PIPELINE
--------
1. Extract the deployed .fnt's embedded TTF (skipped if already done)
2. Patch its cmap with fonttools
3. Read the existing CR2W JSON template, swap fontBuffer.Bytes with the
   base64 of the patched TTF, write modified JSON
4. WolvenKit `convert deserialize` -> new .fnt CR2W
5. Backup old project FNT + old deployed archive
6. Drop new .fnt into project tree
7. WolvenKit `pack` project -> archive.archive
8. Deploy to game's mod folder

Idempotent. Re-run after any future translation rebuild to re-apply the
font fix.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    from fontTools.ttLib import TTFont
except ImportError:                                  # pragma: no cover
    print("[FATAL] fontTools not installed. Install with: pip install fonttools")
    sys.exit(1)

# ── Paths ──────────────────────────────────────────────────────────────────
CLI         = r"C:\Users\Nehoray_Cohen\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
GAME        = r"C:\Game Lab\Cyberpunk 2077"
SCRIPTS_DIR = r"C:\Users\Nehoray_Cohen\Projects\Game translator"
PROJECT     = os.path.join(SCRIPTS_DIR, "תרגום_משחקים")
PROJ_FNT    = os.path.join(
    PROJECT,
    r"source\archive\base\gameplay\gui\fonts\foreign\arabic\ara_es_nawar"
    r"\araesnawar-regular.fnt",
)
PROJ_PACKED = os.path.join(PROJECT, r"packed\archive\pc\mod\archive.archive")
DEPLOY      = os.path.join(GAME, r"archive\pc\mod\z_hebrew_translation.archive")

WORK         = r"C:\Users\Nehoray_Cohen\AppData\Local\Temp\arabic_digits_fix"
RAW_DIR      = os.path.join(WORK, "raw")
JSON_DIR     = os.path.join(WORK, "json")
ENC_DIR      = os.path.join(WORK, "encoded")
TTF_ORIG     = os.path.join(WORK, "heebo_original.ttf")
TTF_PATCHED  = os.path.join(WORK, "heebo_patched.ttf")
FNT_JSON_IN  = os.path.join(JSON_DIR, "araesnawar-regular.fnt.json")
FNT_JSON_OUT = os.path.join(JSON_DIR, "araesnawar-regular_patched.fnt.json")
FNT_CR2W_OUT = os.path.join(ENC_DIR, "araesnawar-regular.fnt")

LOG_FILE = os.path.join(SCRIPTS_DIR, "fix_arabic_digits.log")

WOLVENKIT_TIMEOUT = 600


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def fatal(msg: str) -> None:
    log(f"FATAL: {msg}")
    sys.exit(1)


def run_cli(args, timeout=WOLVENKIT_TIMEOUT):
    try:
        r = subprocess.run(
            [CLI] + args,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout,
        )
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s"
    except Exception as e:                              # pragma: no cover
        return False, f"EXCEPTION: {e}"


# ── Step 1: extract deployed FNT + serialize to JSON (so we keep all
#           non-glyph metadata intact when we swap the TTF bytes) ─────────
def step1_extract_existing_fnt() -> None:
    log("STEP 1: Extract existing deployed FNT + serialize to JSON")
    shutil.rmtree(WORK, ignore_errors=True)
    Path(RAW_DIR).mkdir(parents=True, exist_ok=True)
    Path(JSON_DIR).mkdir(parents=True, exist_ok=True)
    Path(ENC_DIR).mkdir(parents=True, exist_ok=True)

    ok, out = run_cli([
        "extract", DEPLOY,
        "-o", RAW_DIR,
        "-w", "*araesnawar-regular.fnt",
    ])
    if not ok:
        fatal(f"extract failed:\n{out}")
    src = os.path.join(
        RAW_DIR,
        r"base\gameplay\gui\fonts\foreign\arabic\ara_es_nawar\araesnawar-regular.fnt",
    )
    if not os.path.exists(src):
        fatal(f"extract produced no file at {src}")
    log(f"  extracted FNT: {os.path.getsize(src):,} bytes")

    ok, out = run_cli(["convert", "serialize", src, "-o", JSON_DIR])
    if not ok or not os.path.exists(FNT_JSON_IN):
        fatal(f"serialize failed:\n{out}")
    log(f"  serialized to: {FNT_JSON_IN}  ({os.path.getsize(FNT_JSON_IN):,} bytes)")


# ── Step 2: extract TTF bytes from JSON ───────────────────────────────────
def step2_extract_ttf_bytes() -> None:
    log("STEP 2: Extract embedded TTF from FNT JSON")
    with open(FNT_JSON_IN, "r", encoding="utf-8") as f:
        data = json.load(f)
    b64 = data["Data"]["RootChunk"]["fontBuffer"]["Bytes"]
    raw = base64.b64decode(b64)
    Path(TTF_ORIG).write_bytes(raw)
    log(f"  wrote {len(raw):,} bytes -> {TTF_ORIG}")
    if raw[:4] != b"\x00\x01\x00\x00":
        log(f"  WARNING: TTF magic mismatch: {raw[:4]!r}")


# ── Step 3: patch TTF cmap ────────────────────────────────────────────────
def step3_patch_ttf() -> None:
    log("STEP 3: Patch TTF cmap — alias Arabic-Indic digits to Latin 0-9 glyphs")
    font = TTFont(TTF_ORIG)
    cmap = font.getBestCmap()

    # Confirm Latin digits are present — abort if not (would mean upstream
    # font is broken in a way we don't know how to fix).
    for cp in range(0x30, 0x3A):
        if cp not in cmap:
            fatal(f"source TTF is missing Latin digit U+{cp:04X} — can't proceed")
    log(f"  source TTF has all 10 Latin digit glyphs")

    # Find the best Unicode cmap subtable to edit. Prefer Microsoft Unicode
    # BMP (platformID=3, platEncID=1, format=4) — that's what game engines
    # actually query. We add to every Unicode subtable to be defensive.
    digit_glyph_ids = {cp: cmap[cp] for cp in range(0x30, 0x3A)}

    # Confirm needed Latin punctuation glyphs exist too — period, comma, %
    needed_punct = {
        0x2E: "period",      # .
        0x2C: "comma",       # ,
        0x25: "percent",     # %
        0x3B: "semicolon",   # ;
        0x3F: "question",    # ?
    }
    punct_glyph_ids: dict[int, str] = {}
    for cp, name in needed_punct.items():
        if cp not in cmap:
            log(f"  WARN: source TTF missing Latin {name} U+{cp:04X} — skipping its Arabic alias")
            continue
        punct_glyph_ids[cp] = cmap[cp]

    # Aliases: Arabic-locale character → existing Latin glyph
    #   U+0660-0669  Arabic-Indic digits      → Latin 0-9     (the bare-KM root cause)
    #   U+06F0-06F9  Extended Arabic digits   → Latin 0-9     (Persian/Urdu variants)
    #   U+066A       ٪ Arabic Percent Sign    → Latin %        (settings sliders)
    #   U+066B       ٫ Arabic Decimal Sep.    → Latin .        (the "3 6KM" spacing bug)
    #   U+066C       ٬ Arabic Thousands Sep.  → Latin ,        (large numbers)
    #   U+060C       ، Arabic Comma           → Latin ,        (lists)
    #   U+061B       ؛ Arabic Semicolon       → Latin ;        (sentence separators)
    #   U+061F       ؟ Arabic Question Mark   → Latin ?        (prompts)
    aliases: list[tuple[int, int]] = []
    for i in range(10):
        aliases.append((0x0660 + i, 0x30 + i))
        aliases.append((0x06F0 + i, 0x30 + i))
    if 0x25 in punct_glyph_ids: aliases.append((0x066A, 0x25))
    if 0x2E in punct_glyph_ids: aliases.append((0x066B, 0x2E))
    if 0x2C in punct_glyph_ids: aliases.append((0x066C, 0x2C))
    if 0x2C in punct_glyph_ids: aliases.append((0x060C, 0x2C))
    if 0x3B in punct_glyph_ids: aliases.append((0x061B, 0x3B))
    if 0x3F in punct_glyph_ids: aliases.append((0x061F, 0x3F))

    # Additional locale-specific characters identified by the depth audit.
    # U+0640 Tatweel ـ : visible Arabic line-extender — aliased to ASCII
    #                    space so it renders as a tiny gap rather than the
    #                    glaring .notdef rectangle.
    # U+061C ALM      : invisible Arabic Letter Mark (bidi). Alias to U+200E
    #                    LRM (already in the font as a zero-width control)
    #                    so the engine never asks for an unmapped glyph.
    if 0x20 in cmap:    # ASCII space glyph
        aliases.append((0x0640, 0x20))
        # If ALM is missing AND we have LRM, alias them. Else fall back to space.
        target = 0x200E if 0x200E in cmap else 0x20
        if target == 0x200E and 0x200E not in punct_glyph_ids:
            punct_glyph_ids[0x200E] = cmap[0x200E]
        aliases.append((0x061C, target))

    # Combined source-glyph lookup. Also pull in any other Latin/control
    # codepoints we use as alias targets (e.g. ASCII space, LRM control)
    # so they don't KeyError below.
    source_glyph_ids = {**digit_glyph_ids, **punct_glyph_ids}
    for extra_cp in (0x20, 0x200E):
        if extra_cp in cmap and extra_cp not in source_glyph_ids:
            source_glyph_ids[extra_cp] = cmap[extra_cp]

    added_total = 0
    subtable_count = 0
    for sub in font["cmap"].tables:
        if not getattr(sub, "isUnicode", lambda: False)():
            continue
        subtable_count += 1
        before = len(sub.cmap)
        for arabic_cp, latin_cp in aliases:
            sub.cmap[arabic_cp] = source_glyph_ids[latin_cp]
        added = len(sub.cmap) - before
        added_total += added
        log(f"  cmap subtable platformID={sub.platformID} platEncID={sub.platEncID}"
            f" format={sub.format}: +{added} aliases")

    if subtable_count == 0:
        fatal("no Unicode cmap subtables found — cannot patch")
    log(f"  total aliases added across {subtable_count} subtable(s): {added_total}")

    font.save(TTF_PATCHED)
    log(f"  wrote patched TTF: {os.path.getsize(TTF_PATCHED):,} bytes -> {TTF_PATCHED}")

    # Sanity verify by re-opening
    font2 = TTFont(TTF_PATCHED)
    cmap2 = font2.getBestCmap()
    missing = [hex(cp) for cp in range(0x660, 0x66A) if cp not in cmap2]
    if missing:
        fatal(f"verification failed: patched TTF still missing {missing}")
    log(f"  ✓ verified U+0660-U+0669 now resolve in patched TTF")


# ── Step 4: rebuild FNT JSON with patched TTF buffer ──────────────────────
def step4_rebuild_fnt_json() -> None:
    log("STEP 4: Rebuild FNT JSON with patched TTF embedded")
    with open(FNT_JSON_IN, "r", encoding="utf-8") as f:
        data = json.load(f)

    new_bytes = Path(TTF_PATCHED).read_bytes()
    data["Data"]["RootChunk"]["fontBuffer"]["Bytes"] = base64.b64encode(new_bytes).decode("ascii")

    with open(FNT_JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log(f"  wrote {FNT_JSON_OUT}  ({os.path.getsize(FNT_JSON_OUT):,} bytes)")


# ── Step 5: deserialize JSON -> CR2W ───────────────────────────────────────
def step5_deserialize() -> None:
    log("STEP 5: Deserialize patched FNT JSON -> CR2W")
    ok, out = run_cli(["convert", "deserialize", FNT_JSON_OUT, "-o", ENC_DIR])
    if not ok:
        fatal(f"deserialize failed:\n{out}")
    # The deserialize output filename matches the JSON minus ".json"
    candidates = list(Path(ENC_DIR).glob("araesnawar-regular*.fnt"))
    if not candidates:
        fatal(f"deserialize said OK but no FNT in {ENC_DIR}\n{out}")
    # Pick the most recent
    actual = max(candidates, key=lambda p: p.stat().st_mtime)
    if actual.name != "araesnawar-regular.fnt":
        # Rename if WolvenKit appended _patched or similar
        target = Path(ENC_DIR) / "araesnawar-regular.fnt"
        actual.replace(target)
        actual = target
    log(f"  produced: {actual}  ({actual.stat().st_size:,} bytes)")


# ── Step 6: backup + place into project tree ──────────────────────────────
def step6_place_in_project() -> None:
    log("STEP 6: Backup + place patched FNT into project tree")
    if os.path.exists(PROJ_FNT):
        bak = PROJ_FNT + ".bak"
        if not os.path.exists(bak):
            shutil.copy2(PROJ_FNT, bak)
            log(f"  backed up project FNT -> {bak}")
        else:
            log(f"  project FNT backup already exists: {bak}")
    os.makedirs(os.path.dirname(PROJ_FNT), exist_ok=True)
    shutil.copy2(FNT_CR2W_OUT, PROJ_FNT)
    log(f"  placed -> {PROJ_FNT}  ({os.path.getsize(PROJ_FNT):,} bytes)")


# ── Step 7: pack project -> archive.archive ───────────────────────────────
def step7_pack() -> None:
    log("STEP 7: Pack project")
    src_archive = os.path.join(PROJECT, "source", "archive")
    out_dir = os.path.dirname(PROJ_PACKED)
    os.makedirs(out_dir, exist_ok=True)
    if os.path.exists(PROJ_PACKED):
        os.remove(PROJ_PACKED)

    ok, out = run_cli(["pack", src_archive, "-o", out_dir])
    if not ok or not os.path.exists(PROJ_PACKED):
        fatal(f"pack failed:\n{out}")
    log(f"  packed: {PROJ_PACKED}  ({os.path.getsize(PROJ_PACKED):,} bytes)")


# ── Step 8: backup deployed archive + deploy ──────────────────────────────
def step8_deploy() -> None:
    log("STEP 8: Backup deployed archive + deploy new one")
    if os.path.exists(DEPLOY):
        try:
            with open(DEPLOY, "rb"):
                pass
        except PermissionError:
            fatal(f"deploy target is locked (game running?): {DEPLOY}")
        bak = DEPLOY + ".bak"
        # Keep only one .bak (the most recent pre-patch state)
        if os.path.exists(bak):
            os.remove(bak)
        shutil.copy2(DEPLOY, bak)
        log(f"  backed up deployed -> {bak}  ({os.path.getsize(bak):,} bytes)")

    os.makedirs(os.path.dirname(DEPLOY), exist_ok=True)
    shutil.copy2(PROJ_PACKED, DEPLOY)
    log(f"  deployed -> {DEPLOY}  ({os.path.getsize(DEPLOY):,} bytes)")


def main():
    started = time.time()
    log("=" * 72)
    log("fix_arabic_digits_pack starting")
    log("=" * 72)

    for p, name in [(CLI, "WolvenKit CLI"), (GAME, "Game folder"),
                    (PROJECT, "Project folder"), (DEPLOY, "Deployed mod archive")]:
        if not os.path.exists(p):
            fatal(f"missing {name}: {p}")

    step1_extract_existing_fnt()
    step2_extract_ttf_bytes()
    step3_patch_ttf()
    step4_rebuild_fnt_json()
    step5_deserialize()
    step6_place_in_project()
    step7_pack()
    step8_deploy()

    elapsed = time.time() - started
    log("=" * 72)
    log(f"DONE — total {elapsed/60:.1f} min ({int(elapsed)}s)")
    log("=" * 72)


if __name__ == "__main__":
    main()
