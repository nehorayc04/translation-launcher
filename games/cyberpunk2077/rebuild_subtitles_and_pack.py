"""
rebuild_subtitles_and_pack.py
=============================
Surgically re-bake the subtitle CR2W files whose translations changed, then
re-pack and deploy the mod archive.

Why this exists: cp2077_subtitle_batch.py already extracts → applies →
deserializes → packs all 3,083 subtitle files, but a full re-run is hours
of WolvenKit round-tripping. After patch_615_flagged.py corrects a handful
of contaminated entries in localization_translated.json, only the subtitle
FILES that actually contain those entries need re-baking.

This script reuses cp2077_subtitle_batch.py's own phase functions:
  • phase1_extract()      — pristine ar-ar/subtitles extract (idempotent)
  • load_translations()   — current subtitle translations
  • process_one_file()    — serialize → apply → deserialize → place (one file)
  • phase3_pack_deploy()  — pack source/archive → deploy z_hebrew_translation.archive

process_one_file() skips a file when the project already holds it, so each
target's stale project CR2W is deleted first to force a fresh re-bake.

Usage:
    python rebuild_subtitles_and_pack.py                 # read patch_615_report.json
    python rebuild_subtitles_and_pack.py --sections subtitles/media/foo.json,...
    python rebuild_subtitles_and_pack.py --all           # re-bake every subtitle (slow!)
    python rebuild_subtitles_and_pack.py --no-pack       # re-bake only, skip pack/deploy
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Reuse the subtitle batch's machinery wholesale. Importing only runs its
# module-level constants/setup — main() is __name__-guarded.
import cp2077_subtitle_batch as sb  # noqa: E402

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PATCH_REPORT = os.path.join(SCRIPTS_DIR, "patch_615_report.json")
LOG_FILE     = os.path.join(SCRIPTS_DIR, "rebuild_subtitles.log")


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _fresh_stats() -> dict:
    """The stats dict shape process_one_file() expects."""
    return dict(processed=0, skipped_existing=0, skipped_no_hebrew=0,
                missing_source=0, no_changes=0, serialize_failed=0,
                apply_failed=0, deserialize_failed=0, total_fv=0, total_mv=0)


def _dst_cr2w(rel_path: str) -> str:
    """Project CR2W path for a `subtitles/...` section key — mirrors the
    exact formula in cp2077_subtitle_batch.process_one_file()."""
    return os.path.join(sb.PROJ_AR_SUBTITLES,
                        rel_path[len("subtitles/"):].replace("/", os.sep))


def resolve_targets(args) -> list[str]:
    """Determine which subtitle section keys to re-bake."""
    if args.all:
        # Every subtitle section that has translations available.
        return sorted(sb.load_translations().keys())

    if args.sections:
        return [s.strip() for s in args.sections.split(",") if s.strip()]

    if args.sections_file:
        # Comma- or newline-separated section list in a file. Avoids the
        # Windows command-line length limit when hundreds of sections need
        # re-baking (e.g. after a translation cleanup sweep).
        if not os.path.exists(args.sections_file):
            log(f"[!] --sections-file not found: {args.sections_file}")
            return []
        with open(args.sections_file, "r", encoding="utf-8") as f:
            raw = f.read()
        return [s.strip() for s in raw.replace("\n", ",").split(",") if s.strip()]

    # Default: read patch_615_flagged.py's report.
    if not os.path.exists(PATCH_REPORT):
        log(f"[*] No {PATCH_REPORT} and no --sections/--all — nothing to re-bake.")
        return []
    try:
        with open(PATCH_REPORT, "r", encoding="utf-8") as f:
            report = json.load(f)
        targets = list(report.get("patched_sections", {}).get("subtitles", []))
        log(f"[*] patch_615_report.json lists {len(targets)} patched subtitle section(s)")
        return targets
    except (OSError, json.JSONDecodeError) as e:
        log(f"[!] Could not read {PATCH_REPORT}: {e}")
        return []


def main() -> int:
    ap = argparse.ArgumentParser(description="Surgically re-bake + re-pack subtitle CR2W files.")
    ap.add_argument("--sections", help="Comma-separated subtitles/... keys to re-bake.")
    ap.add_argument("--sections-file", dest="sections_file",
                    help="File with a comma/newline-separated subtitles/... key list "
                         "(use when there are too many sections for one CLI arg).")
    ap.add_argument("--all", action="store_true",
                    help="Re-bake EVERY subtitle file (hours of WolvenKit work).")
    ap.add_argument("--no-pack", action="store_true",
                    help="Re-bake the CR2W files only; skip pack + deploy.")
    args = ap.parse_args()

    log("=" * 70)
    log("rebuild_subtitles_and_pack starting")
    log("=" * 70)
    t0 = time.time()

    targets = resolve_targets(args)

    if not targets:
        if args.no_pack:
            log("[*] No targets and --no-pack — nothing to do.")
            return 0
        # Still refresh the deployed archive from the current project tree
        # so a caller asking for a re-pack always gets one.
        log("[*] No subtitle files to re-bake — packing current project tree as-is.")
        ok = sb.phase3_pack_deploy()
        log("=" * 70)
        log(f"DONE (pack-only) — {time.time() - t0:.0f}s")
        return 0 if ok else 1

    # Pristine extract must be present before process_one_file can serialize.
    sb.phase1_extract()

    translations = sb.load_translations()
    stats = _fresh_stats()

    log(f"[*] Re-baking {len(targets)} subtitle file(s) …")
    rebaked = 0
    for i, rel_path in enumerate(targets, 1):
        if not rel_path.startswith("subtitles/"):
            log(f"  [{i}/{len(targets)}] SKIP {rel_path} — not a subtitles/ key")
            continue
        trans_entries = translations.get(rel_path)
        if not trans_entries:
            log(f"  [{i}/{len(targets)}] SKIP {rel_path} — no translations for this section")
            continue
        # Force a fresh re-bake: delete the stale project CR2W so
        # process_one_file()'s resume-skip doesn't short-circuit it.
        dst = _dst_cr2w(rel_path)
        if os.path.exists(dst):
            try:
                os.remove(dst)
            except OSError as e:
                log(f"  [{i}/{len(targets)}] FAIL {rel_path} — cannot remove stale CR2W: {e}")
                continue
        ok, status = sb.process_one_file(rel_path, trans_entries, stats)
        short = rel_path.split("/")[-1][:40]
        if ok:
            rebaked += 1
            log(f"  [{i}/{len(targets)}] OK  {short} ({status})")
        else:
            log(f"  [{i}/{len(targets)}] FAIL {short}: {status}")

    log(f"[*] Re-baked {rebaked}/{len(targets)} file(s). "
        f"fv={stats['total_fv']:,} mv={stats['total_mv']:,}")

    if args.no_pack:
        log("[*] --no-pack — skipping pack + deploy.")
        log("=" * 70)
        log(f"DONE (no pack) — {time.time() - t0:.0f}s")
        return 0

    ok = sb.phase3_pack_deploy()
    log("=" * 70)
    log(f"DONE — re-baked {rebaked}, total {time.time() - t0:.0f}s")
    log("=" * 70)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
