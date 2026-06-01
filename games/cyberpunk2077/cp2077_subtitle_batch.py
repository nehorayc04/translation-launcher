"""
cp2077_subtitle_batch.py
========================
Batch-process all 3,083 subtitle CR2W files through the Arabic-slot pipeline:
  1. Extract pristine ar-ar/subtitles/* from lang_ar_text.archive (one-time)
  2. For each subtitle file:
     a. Serialize CR2W -> text JSON (WolvenKit CLI)
     b. Apply Hebrew translations from localization_translated.json
     c. Deserialize text JSON -> CR2W (WolvenKit CLI)
     d. Place result in project at base/localization/ar-ar/subtitles/...
  3. Pack project, deploy z_hebrew_translation.archive

Designed for unattended overnight runs. Resumable — re-run after a crash and it
picks up where it left off. Skips files that are already in the project.

Logs to subtitle_batch.log next to this script.
"""

import os
import sys
import json
import subprocess
import time
import re
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Optional live-sync to Vercel KV (Redis REST). If deps aren't installed
# or .env isn't set, the feature is silently disabled and the batch keeps
# running normally.
try:
    import requests
    from dotenv import load_dotenv
    _LIVE_SYNC_AVAILABLE = True
except ImportError:
    _LIVE_SYNC_AVAILABLE = False

# ── Paths ─────────────────────────────────────────────────────────────────────
CLI = r"C:\Users\Nehoray_Cohen\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
# The Cyberpunk 2077 copy the user actually launches is the project's own
# staging copy — confirmed 2026-05-20. Deploy MUST land here; an earlier
# "fix" repointed this at C:\Games (a separate install the user never plays),
# so every re-pack vanished into the wrong folder and the user kept seeing a
# stale archive. lang_ar_text.archive (the extraction source) is byte-
# identical across installs, so extracting from here is fine too.
GAME = r"C:\Users\Nehoray_Cohen\Projects\Game translator\Game Lab\Cyberpunk 2077"
PROJ = r"C:\Users\Nehoray_Cohen\Projects\Game translator\תרגום_משחקים"
TRANSLATED_JSON = os.path.join(PROJ, r"source\resources\localization_translated.json")

WORK = r"C:\Users\Nehoray_Cohen\AppData\Local\Temp\subtitle_batch"
EXTRACT_DIR = os.path.join(WORK, "ar_pristine")
TEXT_DIR = os.path.join(WORK, "text")
ENCODED_DIR = os.path.join(WORK, "encoded")

PROJ_AR_SUBTITLES = os.path.join(PROJ, r"source\archive\base\localization\ar-ar\subtitles")
PROJ_PACKED = os.path.join(PROJ, r"packed\archive\pc\mod\archive.archive")
DEPLOY = os.path.join(GAME, r"archive\pc\mod\z_hebrew_translation.archive")

LOG_FILE = os.path.join(os.path.dirname(__file__), "subtitle_batch.log")

# Tolerance: how long any single WolvenKit call can take before we kill it
WOLVENKIT_TIMEOUT_SEC = 120

HEBREW_RE = re.compile(r"[֐-׿]")

# ── Vercel KV live-sync ─────────────────────────────────────────────────────
# Reads KV_REST_API_URL and KV_REST_API_TOKEN from <scripts dir>/.env. The push
# is throttled to once every PUSH_INTERVAL_SEC seconds and never crashes the
# batch — any failure prints "[!] Live sync skipped" and continues.
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_KV_URL = None
_KV_TOKEN = None
if _LIVE_SYNC_AVAILABLE:
    try:
        load_dotenv(os.path.join(_SCRIPTS_DIR, ".env"))
        _KV_URL = os.environ.get("KV_REST_API_URL")
        _KV_TOKEN = os.environ.get("KV_REST_API_TOKEN")
    except Exception:
        pass
_LIVE_SYNC_READY = bool(_LIVE_SYNC_AVAILABLE and _KV_URL and _KV_TOKEN)
PUSH_INTERVAL_SEC = 900  # push translation_stats every 15 minutes
_last_push_time = 0.0


def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def progress_bar(processed, total, t_start, width=40):
    """Return a single-line progress bar string with percentage, count, rate, ETA."""
    elapsed = time.time() - t_start
    rate = processed / elapsed if elapsed > 0 else 0.0
    eta_sec = (total - processed) / rate if rate > 0 else 0
    pct = (processed / total * 100) if total else 0.0
    filled = int(width * processed / max(total, 1))
    bar = "#" * filled + "-" * (width - filled)
    return (
        f"[{bar}] {pct:5.1f}%  {processed:>5,}/{total:<5,}  "
        f"rate={rate:.2f}/s  ETA {eta_sec / 3600:.1f}h"
    )


def push_stats_to_vercel(processed, total, t_start):
    """POST current subtitle-batch progress to Vercel KV. Silent on every
    failure path (missing .env, network error, timeout) — just logs
    '[!] Live sync skipped' and returns."""
    if not _LIVE_SYNC_READY:
        log("[!] Live sync skipped")
        return
    try:
        elapsed = time.time() - t_start
        rate_per_sec = processed / elapsed if elapsed > 0 else 0
        payload = {
            "gameId": "cyberpunk",
            "gpuModel": "AMD Radeon RX 9070 16GB",
            "aiModel": "Gemma-2 27B",
            "linesTranslated": processed,
            "linesTotal": total,
            "gpuRatePerHour": int(rate_per_sec * 3600),
            "updatedAt": int(time.time() * 1000),
        }
        requests.post(
            f"{_KV_URL}/set/translation_stats",
            headers={"Authorization": f"Bearer {_KV_TOKEN}"},
            data=json.dumps(payload),
            timeout=5,
        )
    except Exception:
        log("[!] Live sync skipped")


def run_cli(args, timeout=WOLVENKIT_TIMEOUT_SEC):
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
    except Exception as e:
        return False, f"EXCEPTION: {e}"


# ── Phase 1: bulk extract ─────────────────────────────────────────────────────
def phase1_extract():
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    marker = os.path.join(EXTRACT_DIR, ".extracted_done")
    if os.path.exists(marker):
        log("Phase 1: Already extracted (marker present), skipping")
        return

    log("Phase 1: Extracting all subtitle CR2W files from lang_ar_text.archive (one-time)")
    archive_path = os.path.join(GAME, r"archive\pc\content\lang_ar_text.archive")
    ok, out = run_cli(
        ["extract", archive_path, "-o", EXTRACT_DIR, "-w", "*subtitles*"],
        timeout=900,
    )
    if not ok:
        log(f"Phase 1 FAILED: {out[-500:]}")
        sys.exit(1)

    n = sum(1 for _ in Path(EXTRACT_DIR).rglob("*.json"))
    log(f"  Extracted {n:,} subtitle CR2W files")
    Path(marker).touch()


# ── Phase 2: per-file pipeline ────────────────────────────────────────────────
def load_translations():
    log(f"Loading translations: {TRANSLATED_JSON}")
    with open(TRANSLATED_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Filter to subtitles only
    subs = {k: v for k, v in data.items() if k.startswith("subtitles/")}
    log(f"  {len(subs):,} subtitle files have translations available")
    return subs


def apply_translations_to_text_json(wkit_json_path, trans_entries):
    """Apply Hebrew translations to a WolvenKit text-JSON file in place.
    Returns (matched_count, fv_updated, mv_updated).
    """
    with open(wkit_json_path, "r", encoding="utf-8") as f:
        wkit = json.load(f)

    # Build lookup
    lookup = {}
    for e in trans_entries:
        pk = e.get("primaryKey", 0)
        lookup[str(pk)] = e
        if isinstance(pk, str) and pk.isdigit():
            lookup[int(pk)] = e
        elif isinstance(pk, int):
            lookup[pk] = e

    try:
        entries = wkit["Data"]["RootChunk"]["root"]["Data"]["entries"]
    except (KeyError, TypeError):
        return 0, 0, 0

    matched = fv = mv = 0
    for entry in entries:
        # Subtitle entries use 'stringId' (string); onscreen entries use 'primaryKey' (int).
        # Try both — subtitle CR2W lacks primaryKey field entirely.
        pk = entry.get("primaryKey")
        if pk is None:
            pk = entry.get("stringId")
        if pk is None:
            continue
        t = lookup.get(str(pk)) or lookup.get(pk)
        if not t:
            continue
        matched += 1
        new_fv = (t.get("femaleVariant") or "").strip()
        new_mv = (t.get("maleVariant") or "").strip()
        # If we only have one Hebrew variant (typical for subtitles), use it for BOTH
        # gender slots so we replace the Arabic mv too — otherwise mv stays Arabic.
        if new_fv and not new_mv and HEBREW_RE.search(new_fv):
            new_mv = new_fv
        elif new_mv and not new_fv and HEBREW_RE.search(new_mv):
            new_fv = new_mv

        if new_fv and HEBREW_RE.search(new_fv) and new_fv != entry.get("femaleVariant", ""):
            entry["femaleVariant"] = new_fv
            fv += 1
        if new_mv and HEBREW_RE.search(new_mv) and new_mv != entry.get("maleVariant", ""):
            entry["maleVariant"] = new_mv
            mv += 1

    if fv > 0 or mv > 0:
        with open(wkit_json_path, "w", encoding="utf-8") as f:
            json.dump(wkit, f, ensure_ascii=False, indent=2)

    return matched, fv, mv


def process_one_file(rel_path, trans_entries, stats):
    """Process a single subtitle file end-to-end."""
    src_cr2w = os.path.join(EXTRACT_DIR, "base", "localization", "ar-ar", rel_path.replace("/", os.sep))
    dst_cr2w = os.path.join(PROJ_AR_SUBTITLES, rel_path[len("subtitles/"):].replace("/", os.sep))

    # Resume support: skip if project already has this file
    if os.path.exists(dst_cr2w) and os.path.getsize(dst_cr2w) > 100:
        stats["skipped_existing"] += 1
        return True, "skip_existing"

    if not os.path.exists(src_cr2w):
        stats["missing_source"] += 1
        return False, f"no source CR2W at {src_cr2w}"

    if not trans_entries or not any(HEBREW_RE.search(e.get("femaleVariant", "") or "")
                                     for e in trans_entries):
        stats["skipped_no_hebrew"] += 1
        return True, "no_hebrew_translations"

    # Use a per-file temp dir to keep WolvenKit output isolated
    fname = os.path.basename(src_cr2w)
    temp_text_dir = os.path.join(TEXT_DIR, "_per_file")
    temp_enc_dir = os.path.join(ENCODED_DIR, "_per_file")
    os.makedirs(temp_text_dir, exist_ok=True)
    os.makedirs(temp_enc_dir, exist_ok=True)
    temp_txt = os.path.join(temp_text_dir, fname + ".json")
    temp_enc = os.path.join(temp_enc_dir, fname)

    # Clean any prior temp files
    for p in (temp_txt, temp_enc):
        if os.path.exists(p):
            os.remove(p)

    # Step a: serialize CR2W -> text JSON
    ok, out = run_cli(["convert", "serialize", src_cr2w, "-o", temp_text_dir])
    if not ok or not os.path.exists(temp_txt):
        stats["serialize_failed"] += 1
        return False, f"serialize: {out[-200:]}"

    # Step b: apply translations
    try:
        matched, fv, mv = apply_translations_to_text_json(temp_txt, trans_entries)
    except Exception as e:
        stats["apply_failed"] += 1
        return False, f"apply: {e}"

    if fv == 0 and mv == 0:
        stats["no_changes"] += 1
        # Clean and skip — no Hebrew applied so nothing to ship
        os.remove(temp_txt)
        return True, "no_changes_applied"

    # Step c: deserialize text JSON -> CR2W
    ok, out = run_cli(["convert", "deserialize", temp_txt, "-o", temp_enc_dir])
    if not ok or not os.path.exists(temp_enc):
        stats["deserialize_failed"] += 1
        return False, f"deserialize: {out[-200:]}"

    # Step d: move to project
    os.makedirs(os.path.dirname(dst_cr2w), exist_ok=True)
    if os.path.exists(dst_cr2w):
        os.remove(dst_cr2w)
    os.replace(temp_enc, dst_cr2w)

    # Cleanup temp text
    if os.path.exists(temp_txt):
        os.remove(temp_txt)

    stats["processed"] += 1
    stats["total_fv"] += fv
    stats["total_mv"] += mv
    return True, f"ok fv={fv} mv={mv}"


def phase2_loop():
    translations = load_translations()
    all_subtitle_keys = sorted(translations.keys())
    log(f"Phase 2: Processing {len(all_subtitle_keys):,} subtitle files...")

    stats = dict(processed=0, skipped_existing=0, skipped_no_hebrew=0,
                 missing_source=0, no_changes=0, serialize_failed=0,
                 apply_failed=0, deserialize_failed=0,
                 total_fv=0, total_mv=0)

    t_start = time.time()
    n_total = len(all_subtitle_keys)

    global _last_push_time
    _last_push_time = 0.0  # force first push as soon as loop starts

    for idx, rel_path in enumerate(all_subtitle_keys, 1):
        ok, status = process_one_file(rel_path, translations[rel_path], stats)

        # Per-file failure line stays as-is so problems are obvious
        if not ok:
            log(f"  [{idx}/{n_total}] FAIL {rel_path}: {status}")

        # Visible progress bar every 25 files (plus first + last)
        if idx == 1 or idx % 25 == 0 or idx == n_total:
            failed = (
                stats["serialize_failed"]
                + stats["deserialize_failed"]
                + stats["apply_failed"]
            )
            log(
                f"  {progress_bar(idx, n_total, t_start)}  "
                f"(processed={stats['processed']} "
                f"skipped={stats['skipped_existing']} failed={failed})"
            )

        # Throttled live-sync push to Vercel KV
        if time.time() - _last_push_time >= PUSH_INTERVAL_SEC:
            push_stats_to_vercel(idx, n_total, t_start)
            _last_push_time = time.time()

    log("")
    log("Phase 2 stats:")
    for k, v in stats.items():
        log(f"  {k}: {v:,}")
    return stats


# ── Phase 3: pack and deploy ──────────────────────────────────────────────────
def backup_before_deploy():
    """Back up the current translation archive into a timestamped
    archive\\pc\\mod_backups\\ folder before it is overwritten. Only
    z_hebrew_translation.archive is copied — the other mods in mod\\ are
    never touched by this pipeline."""
    import shutil
    import time
    if not os.path.exists(DEPLOY):
        log("  no existing archive to back up (first deploy)")
        return
    bdir = os.path.join(GAME, "archive", "pc", "mod_backups",
                        time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(bdir, exist_ok=True)
    dst = os.path.join(bdir, os.path.basename(DEPLOY))
    shutil.copy2(DEPLOY, dst)
    log(f"  backed up -> {dst}  ({os.path.getsize(dst):,} bytes)")


def phase3_pack_deploy():
    log("Phase 3: Packing project")
    if os.path.exists(PROJ_PACKED):
        os.remove(PROJ_PACKED)

    src_archive = os.path.join(PROJ, "source", "archive")
    out_dir = os.path.dirname(PROJ_PACKED)
    os.makedirs(out_dir, exist_ok=True)

    ok, out = run_cli(["pack", src_archive, "-o", out_dir], timeout=600)
    if not ok or not os.path.exists(PROJ_PACKED):
        log(f"Pack FAILED: {out[-500:]}")
        sys.exit(1)

    size = os.path.getsize(PROJ_PACKED)
    log(f"  Packed: {PROJ_PACKED} ({size:,} bytes)")

    log("Phase 3: Deploying to game mod folder")
    backup_before_deploy()
    # Make sure no game process holds the file
    if os.path.exists(DEPLOY):
        try:
            os.remove(DEPLOY)
        except PermissionError:
            log("  WARNING: deploy target is locked (game running?)")
            return False

    import shutil
    shutil.copy2(PROJ_PACKED, DEPLOY)
    log(f"  Deployed: {DEPLOY} ({os.path.getsize(DEPLOY):,} bytes)")
    return True


def main():
    log("=" * 70)
    log("cp2077_subtitle_batch starting")
    log("=" * 70)

    # Sanity checks
    for path, name in [(CLI, "WolvenKit CLI"), (GAME, "Game folder"), (PROJ, "Project"), (TRANSLATED_JSON, "Translations JSON")]:
        if not os.path.exists(path):
            log(f"FATAL: missing {name} at {path}")
            sys.exit(1)

    os.makedirs(WORK, exist_ok=True)
    os.makedirs(PROJ_AR_SUBTITLES, exist_ok=True)

    phase1_extract()
    stats = phase2_loop()
    phase3_pack_deploy()

    log("")
    log("=" * 70)
    log("cp2077_subtitle_batch DONE")
    log(f"  Total processed: {stats['processed']:,}")
    log(f"  Total Hebrew strings injected: fv={stats['total_fv']:,} mv={stats['total_mv']:,}")
    log("=" * 70)


if __name__ == "__main__":
    main()
