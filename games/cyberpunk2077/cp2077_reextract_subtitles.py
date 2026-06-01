"""
cp2077_reextract_subtitles.py
=============================
Re-extract English subtitle dialogue text using WolvenKit's canonical decode
(replacing the original buggy cp2077_extract.py output for subtitle entries).

Why: cp2077_extract.py used hardcoded CName indices for `primaryKey` etc. That
worked for onscreens but missed `localizationPersistenceSubtitleEntry` entries
which use `stringId` instead of `primaryKey` and a different CName layout.
Result: ~60-90k subtitle dialogue entries had empty `femaleVariant` in
`localization_translated.json` — nothing for the LM Studio translator to translate.

This script:
  1. Extracts all subtitle CR2W files from lang_en_text.archive (one-time)
  2. Serializes each one to text JSON via WolvenKit (folder mode if possible)
  3. Parses each text JSON to extract: stringId -> {fv, mv} English text
  4. Updates localization_translated.json:
       - For each subtitle entry currently lacking text (fv == ''),
         set fv = English source text from the WolvenKit JSON.
       - Atomic write so a crash mid-script can't corrupt the file.
  5. Backs up the original localization_translated.json first.

After this script: re-run cp2077_fix_missing_translations.py and the LM Studio
translator will have actual English source text to translate.
"""

import os
import sys
import json
import shutil
import subprocess
import time
import re
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


CLI = r"C:\Users\Nehoray_Cohen\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
GAME = r"C:\Users\Nehoray_Cohen\Projects\Game translator\Game Lab\Cyberpunk 2077"
PROJ = r"C:\Users\Nehoray_Cohen\Projects\Game translator\תרגום_משחקים"
TRANSLATED_JSON = os.path.join(PROJ, r"source\resources\localization_translated.json")
EXPORT_JSON = os.path.join(PROJ, r"source\resources\localization_export.json")
ARCHIVE = os.path.join(GAME, r"archive\pc\content\lang_en_text.archive")

WORK = r"C:\Users\Nehoray_Cohen\AppData\Local\Temp\reextract_subs"
EXTRACT_DIR = os.path.join(WORK, "en_pristine")
TEXT_DIR = os.path.join(WORK, "text")

LOG_FILE = os.path.join(os.path.dirname(__file__), "reextract_subtitles.log")

HEBREW_RE = re.compile(r"[֐-׿]")


def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run_cli(args, timeout=600):
    try:
        r = subprocess.run([CLI] + args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s"
    except Exception as e:
        return False, f"EXCEPTION: {e}"


# ── Phase 1: extract all en-us subtitle CR2W files ────────────────────────────
def phase1_extract():
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    marker = os.path.join(EXTRACT_DIR, ".extracted_done")
    if os.path.exists(marker):
        log("Phase 1: en-us subtitles already extracted, skipping")
        return

    log("Phase 1: Extracting all en-us subtitle CR2W files (one-time)")
    ok, out = run_cli(
        ["extract", ARCHIVE, "-o", EXTRACT_DIR, "-w", "*subtitles*"],
        timeout=900,
    )
    if not ok:
        log(f"Phase 1 FAILED: {out[-500:]}")
        sys.exit(1)
    n = sum(1 for _ in Path(EXTRACT_DIR).rglob("*.json"))
    log(f"  Extracted {n:,} subtitle CR2W files")
    Path(marker).touch()


# ── Phase 2: serialize all subtitles to text JSON ─────────────────────────────
def phase2_serialize_all():
    """Serialize each subtitle CR2W to text JSON. Resumable: skips files already done."""
    os.makedirs(TEXT_DIR, exist_ok=True)
    marker = os.path.join(TEXT_DIR, ".serialize_done")
    if os.path.exists(marker):
        log("Phase 2: serialize already done, skipping")
        return

    src_root = os.path.join(EXTRACT_DIR, "base", "localization", "en-us", "subtitles")
    cr2w_files = list(Path(src_root).rglob("*.json"))
    log(f"Phase 2: Serializing {len(cr2w_files):,} subtitle CR2W files")

    t0 = time.time()
    done = 0
    failed = 0

    for idx, src in enumerate(cr2w_files, 1):
        # Mirror folder structure under TEXT_DIR
        rel = src.relative_to(src_root)
        out_dir = Path(TEXT_DIR) / rel.parent
        out_path = out_dir / (rel.name + ".json")

        if out_path.exists() and out_path.stat().st_size > 100:
            done += 1
            continue

        out_dir.mkdir(parents=True, exist_ok=True)
        ok, msg = run_cli(["convert", "serialize", str(src), "-o", str(out_dir)], timeout=120)
        if not ok:
            failed += 1
            if failed <= 5:
                log(f"  [{idx}/{len(cr2w_files)}] FAIL serialize {src.name}: {msg[-150:]}")
        else:
            done += 1

        if idx % 50 == 0 or idx == len(cr2w_files):
            elapsed = time.time() - t0
            rate = idx / elapsed if elapsed > 0 else 0
            eta = (len(cr2w_files) - idx) / rate if rate > 0 else 0
            log(f"  [{idx:,}/{len(cr2w_files):,}] done={done} failed={failed} rate={rate:.2f}/s ETA={eta/3600:.1f}h")

    log(f"Phase 2 complete: {done} serialized, {failed} failed")
    Path(marker).touch()


# ── Phase 3: parse text JSONs → update localization_translated.json ───────────
def phase3_update_translations():
    log("Phase 3: Parsing text JSONs and updating localization_translated.json")

    backup = TRANSLATED_JSON + f".bak.{int(time.time())}"
    log(f"  Backing up: {backup}")
    shutil.copy2(TRANSLATED_JSON, backup)

    log("  Loading translations...")
    with open(TRANSLATED_JSON, "r", encoding="utf-8") as f:
        tr = json.load(f)

    log("  Loading export (for primaryKey reference)...")
    with open(EXPORT_JSON, "r", encoding="utf-8") as f:
        src = json.load(f)

    text_root = Path(TEXT_DIR)
    text_files = list(text_root.rglob("*.json"))
    log(f"  Processing {len(text_files):,} text JSONs")

    files_updated = 0
    entries_added_text = 0
    entries_already_had_text = 0

    for tf in text_files:
        # Reconstruct relative path: TEXT_DIR/quest/q001/q001_xx.json -> subtitles/quest/q001/q001_xx.json (strip .json suffix at end? actually WolvenKit appends .json to whatever, so original .json + .json suffix. Strip the trailing .json once.)
        rel = tf.relative_to(text_root)
        # WolvenKit's serialize output is named like "<original_filename>.json"
        # so original was something.json and now is something.json.json
        rel_str = str(rel).replace(os.sep, "/")
        # Strip trailing ".json" appended by WolvenKit
        if rel_str.endswith(".json.json"):
            rel_str = rel_str[:-5]

        json_key = "subtitles/" + rel_str

        if json_key not in tr:
            continue

        try:
            with open(tf, "r", encoding="utf-8") as f:
                wkit = json.load(f)
            entries = wkit["Data"]["RootChunk"]["root"]["Data"]["entries"]
        except (KeyError, TypeError, json.JSONDecodeError) as ex:
            continue

        # Build stringId -> (fv, mv) lookup from the WolvenKit text JSON
        wkit_lookup = {}
        for e in entries:
            sid = e.get("stringId") or e.get("primaryKey")
            if sid is None:
                continue
            wkit_lookup[str(sid)] = (
                (e.get("femaleVariant") or "").strip(),
                (e.get("maleVariant") or "").strip(),
            )

        # Walk our translations entries, fill empty fv/mv from WolvenKit data
        # (but don't overwrite if we already have Hebrew there)
        tr_entries = tr[json_key]
        any_updated = False
        for te in tr_entries:
            pk = te.get("primaryKey")
            wfv, wmv = wkit_lookup.get(str(pk), ("", ""))

            cur_fv = (te.get("femaleVariant") or "").strip()
            cur_mv = (te.get("maleVariant") or "").strip()

            # If our entry is empty but WolvenKit has the English source, store it
            if not cur_fv and wfv and not HEBREW_RE.search(wfv):
                te["femaleVariant"] = wfv
                entries_added_text += 1
                any_updated = True
            elif cur_fv:
                entries_already_had_text += 1

            if not cur_mv and wmv and not HEBREW_RE.search(wmv):
                te["maleVariant"] = wmv
                # Don't double-count

        if any_updated:
            files_updated += 1

    log(f"  Files updated: {files_updated:,}")
    log(f"  Entries with new English source text: {entries_added_text:,}")
    log(f"  Entries that already had text: {entries_already_had_text:,}")

    log("  Atomic save...")
    tmp = TRANSLATED_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(tr, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TRANSLATED_JSON)
    log("  [OK] Saved")


def main():
    log("=" * 70)
    log("cp2077_reextract_subtitles starting")
    log("=" * 70)

    for p, n in [(CLI, "WolvenKit CLI"), (GAME, "Game"), (PROJ, "Project"),
                  (TRANSLATED_JSON, "translations JSON"), (EXPORT_JSON, "export JSON")]:
        if not os.path.exists(p):
            log(f"FATAL: missing {n}: {p}")
            sys.exit(1)

    os.makedirs(WORK, exist_ok=True)

    phase1_extract()
    phase2_serialize_all()
    phase3_update_translations()

    log("=" * 70)
    log("cp2077_reextract_subtitles DONE")
    log("Now run: python cp2077_fix_missing_translations.py  (LM Studio translation)")
    log("Then run: python cp2077_subtitle_batch.py  (apply translations + pack + deploy)")
    log("=" * 70)


if __name__ == "__main__":
    main()
