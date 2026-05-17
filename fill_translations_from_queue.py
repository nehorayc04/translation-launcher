"""
fill_translations_from_queue.py
================================
Merge translation entries into `localization_translated.json` in BOTH
onscreens sections (onscreens.json + onscreens_final.json) in one shot.

TWO MODES

  1. English fallback (immediate playability):
         python fill_translations_from_queue.py --english-fallback
     Reads `missing_translations_queue.json` and inserts the original
     English text as the translation for every missing primary key. The
     Heebo font we deployed already covers Latin glyphs, so these strings
     render legibly (English) instead of invisibly (Arabic .notdef).

  2. LM-Studio batch merge (Hebrew translations):
         python fill_translations_from_queue.py path/to/lm_output.json
     Reads a translated batch and merges Hebrew text. The input may be:
       (a) `{ "onscreens/onscreens.json": [ {primaryKey, femaleVariant, maleVariant}, ... ] }`
       (b) `[ {primaryKey, femaleVariant, maleVariant}, ... ]`  (flat list applied to both sections)
       (c) the missing-queue schema enriched with a `hebrew_female` /
           `hebrew_male` field per entry.

OPTIONS
  --no-overwrite     Skip primary keys that already have non-empty text in
                     `localization_translated.json` (default for English
                     fallback — never wipe a Hebrew translation).
  --overwrite        Overwrite existing non-empty entries (default for LM
                     Studio merge — those ARE real translations).
  --rebuild          After merging, run `rebuild_onscreens_and_pack.py` to
                     repack + deploy the mod archive.
  --dry-run          Show counts and a sample diff without writing anything.

A timestamped backup of `localization_translated.json` is taken before
any write — kept next to the original (e.g. `…json.bak.fill.1716025330`).

Idempotent.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPTS_DIR = r"C:\Users\nc528\סקריפטים\תרגום משחקים"
PROJECT     = os.path.join(SCRIPTS_DIR, "תרגום_משחקים")
TRANSLATED  = os.path.join(PROJECT, r"source\resources\localization_translated.json")
QUEUE       = os.path.join(SCRIPTS_DIR, "missing_translations_queue.json")
REBUILD     = os.path.join(SCRIPTS_DIR, "rebuild_onscreens_and_pack.py")

# The two sections the engine reads from on the ar-ar slot. Both must
# carry the same translations because they are sister files in the
# vanilla archive (identical schema, identical key set).
ONSCREENS_SECTIONS = ["onscreens/onscreens.json", "onscreens/onscreens_final.json"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def is_nonempty(entry: dict) -> bool:
    fem = (entry.get("femaleVariant") or "").strip()
    mal = (entry.get("maleVariant") or "").strip()
    return bool(fem or mal)


def index_by_pk(entries: list) -> dict:
    return {str(e["primaryKey"]): e for e in entries if e.get("primaryKey") is not None}


def load_english_fallback_entries() -> dict:
    """Returns {section: [{primaryKey, secondaryKey, femaleVariant, maleVariant}]}
    where femaleVariant/maleVariant are the original English strings."""
    if not os.path.exists(QUEUE):
        sys.exit(f"FATAL: missing queue file {QUEUE}. Run audit_all_missing_translations.py first.")
    with open(QUEUE, "r", encoding="utf-8") as f:
        q = json.load(f)
    out = {}
    for section, entries in q.get("missing", {}).items():
        out[section] = []
        for e in entries:
            out[section].append({
                "primaryKey":    e["primaryKey"],
                "secondaryKey":  e.get("secondaryKey", "") or "",
                "femaleVariant": e.get("english_female", "") or "",
                "maleVariant":   e.get("english_male", "") or "",
            })
    return out


def load_lm_studio_batch(path: str) -> dict:
    """Normalize to {section: [entries]}. Accepts shapes (a)(b)(c) from
    the docstring."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Shape (b): flat list of entries — apply to both onscreens sections
    if isinstance(data, list):
        normalized = _coerce_entries(data)
        return {s: list(normalized) for s in ONSCREENS_SECTIONS}

    # Shape (c): queue schema with hebrew_female / hebrew_male fields
    if isinstance(data, dict) and "missing" in data:
        out = {}
        for section, entries in data["missing"].items():
            normalized = []
            for e in entries:
                fem = e.get("hebrew_female", "") or e.get("femaleVariant", "") or ""
                mal = e.get("hebrew_male", "")   or e.get("maleVariant", "")   or ""
                if not (fem or mal):
                    continue  # entry hasn't been translated yet
                normalized.append({
                    "primaryKey":    e["primaryKey"],
                    "secondaryKey":  e.get("secondaryKey", "") or "",
                    "femaleVariant": fem,
                    "maleVariant":   mal,
                })
            out[section] = normalized
        return out

    # Shape (a): {section: [entries]}
    if isinstance(data, dict):
        return {s: _coerce_entries(v) for s, v in data.items()}

    sys.exit(f"FATAL: unrecognized input schema in {path}")


def _coerce_entries(items: list) -> list:
    out = []
    for e in items:
        pk = e.get("primaryKey")
        if pk is None:
            continue
        out.append({
            "primaryKey":    pk,
            "secondaryKey":  e.get("secondaryKey", "") or "",
            "femaleVariant": e.get("femaleVariant", e.get("hebrew_female", "")) or "",
            "maleVariant":   e.get("maleVariant",   e.get("hebrew_male",   "")) or "",
        })
    return out


def merge(translated: dict, new_by_section: dict, *, overwrite: bool) -> dict:
    """In-place merge of new_by_section into translated. Returns stats."""
    stats = {"added": 0, "updated": 0, "kept": 0, "skipped_other_section": 0}

    for section, new_entries in new_by_section.items():
        if section not in ONSCREENS_SECTIONS:
            # The audit queue and most LM batches will be onscreens-only.
            # If a batch targets a different section (e.g. a specific
            # subtitle file), we DO merge it — but won't auto-duplicate
            # across the two onscreens sections.
            sections_to_write = [section]
        else:
            # Always mirror onscreens entries into both sister sections.
            sections_to_write = ONSCREENS_SECTIONS

        for write_section in sections_to_write:
            existing = translated.setdefault(write_section, [])
            idx = index_by_pk(existing)
            for new_e in new_entries:
                pk = str(new_e["primaryKey"])
                cur = idx.get(pk)
                if cur is None:
                    existing.append(new_e)
                    idx[pk] = new_e
                    stats["added"] += 1
                else:
                    if is_nonempty(cur) and not overwrite:
                        stats["kept"] += 1
                        continue
                    cur["secondaryKey"]  = new_e.get("secondaryKey", cur.get("secondaryKey", ""))
                    cur["femaleVariant"] = new_e["femaleVariant"]
                    cur["maleVariant"]   = new_e["maleVariant"]
                    stats["updated"] += 1
    return stats


def backup(path: str) -> str:
    bak = f"{path}.bak.fill.{int(time.time())}"
    log(f"backing up -> {bak}")
    # File is ~40 MB; OS-level copy is faster than re-serializing.
    with open(path, "rb") as src, open(bak, "wb") as dst:
        for chunk in iter(lambda: src.read(1 << 20), b""):
            dst.write(chunk)
    return bak


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("input", nargs="?",
                   help="LM Studio output JSON (omit when using --english-fallback)")
    p.add_argument("--english-fallback", action="store_true",
                   help="Fill missing keys with the original English text from "
                        "missing_translations_queue.json")
    overwrite = p.add_mutually_exclusive_group()
    overwrite.add_argument("--overwrite", action="store_true",
                           help="Overwrite existing non-empty entries")
    overwrite.add_argument("--no-overwrite", action="store_true",
                           help="Preserve existing non-empty entries (default for "
                                "--english-fallback)")
    p.add_argument("--rebuild", action="store_true",
                   help="Run rebuild_onscreens_and_pack.py after merging")
    p.add_argument("--dry-run", action="store_true",
                   help="Show counts only; do not write")
    args = p.parse_args()

    if not args.english_fallback and not args.input:
        p.error("provide an input file or pass --english-fallback")

    # Defaults:
    #   English fallback -> never overwrite (real Hebrew always wins).
    #   LM Studio batch  -> overwrite (those ARE real translations).
    if args.overwrite:
        overwrite_flag = True
    elif args.no_overwrite:
        overwrite_flag = False
    else:
        overwrite_flag = not args.english_fallback

    log(f"mode: {'ENGLISH FALLBACK' if args.english_fallback else 'LM-Studio merge'}")
    log(f"overwrite existing non-empty: {overwrite_flag}")

    if args.english_fallback:
        new_by_section = load_english_fallback_entries()
    else:
        new_by_section = load_lm_studio_batch(args.input)
    total_new = sum(len(v) for v in new_by_section.values())
    log(f"loaded {total_new:,} candidate translations across {len(new_by_section)} section(s)")

    log("loading current translation file…")
    with open(TRANSLATED, "r", encoding="utf-8") as f:
        translated = json.load(f)
    log(f"  sections: {len(translated):,}")

    stats = merge(translated, new_by_section, overwrite=overwrite_flag)
    log(f"merge stats: added={stats['added']:,}  updated={stats['updated']:,}  "
        f"kept_existing={stats['kept']:,}")

    if args.dry_run:
        log("DRY-RUN — not writing")
        return

    backup(TRANSLATED)
    log(f"writing {TRANSLATED}")
    with open(TRANSLATED, "w", encoding="utf-8") as f:
        json.dump(translated, f, ensure_ascii=False, indent=2)
    log(f"  size: {os.path.getsize(TRANSLATED):,} bytes")

    if args.rebuild:
        log("=" * 60)
        log("Chaining rebuild_onscreens_and_pack.py")
        log("=" * 60)
        r = subprocess.run([sys.executable, REBUILD])
        if r.returncode != 0:
            sys.exit(f"rebuild failed (exit {r.returncode})")
        log("rebuild + deploy complete")


if __name__ == "__main__":
    main()
