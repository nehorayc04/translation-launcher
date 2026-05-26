"""
audit_all_missing_translations.py
=================================
Exhaustive cross-reference of the *true* English source data against the
current Hebrew translation file. Identifies every primaryKey that exists
in English (with a non-empty string) and is either absent from our
translation or has both variants empty.

WHY TRUTH IS AUGMENTED
----------------------
`localization_export.json` was produced by an earlier extraction run and
turned out to be **incomplete**: it lists 44,998 onscreens entries while
the game's actual `lang_en_text.archive/onscreens_final.json` has 60,296.
~15,300 strings (settings labels, quest objectives, item names, etc.)
are absent from the export entirely — that's the entire reason the
settings buttons and Mr. Hands quest text rendered blank in-game.

So we don't trust the export alone. We augment it with fresh extracts of
the engine's *actual* onscreens files (base game + ep1 DLC), and union
that with the export for the cross-reference.

EXCLUSIONS
----------
- `stringidvariantlengthsreport.json` — CDPR-internal QA report.
- `voiceovermap*.json` — binary audio cue maps with NUL-byte keys/values.
  Not translatable text.

INPUTS
  user-curated EN export:  תרגום_משחקים/source/resources/localization_export.json
  current HE state:        תרגום_משחקים/source/resources/localization_translated.json
  live truth (extracted):  C:/Users/.../Temp/audit_truth/...
    └─ base game  onscreens.json + onscreens_final.json
    └─ ep1 DLC    onscreens.json + onscreens_final.json (if archive exists)

OUTPUTS
  missing_translations_queue.json   — ready to feed into the LM Studio batch
  audit_missing_report.txt          — human-readable summary

Run from project root:
    python audit_all_missing_translations.py

Idempotent. Overwrites outputs each run. Extracted-truth cache is reused
across runs; pass --refresh to force re-extraction.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPTS_DIR = r"C:\Users\nc528\סקריפטים\תרגום משחקים"
PROJECT     = os.path.join(SCRIPTS_DIR, "תרגום_משחקים")
GAME        = os.path.join(SCRIPTS_DIR, "Cyberpunk 2077")
CLI         = r"C:\Users\nc528\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"

EXPORT      = os.path.join(PROJECT, r"source\resources\localization_export.json")
TRANSLATED  = os.path.join(PROJECT, r"source\resources\localization_translated.json")

# Live extract cache (pristine EN onscreens + onscreens_final + ep1 versions)
TRUTH_CACHE = r"C:\Users\nc528\AppData\Local\Temp\audit_truth"

# Game archives that hold the engine-visible English onscreens text
EN_BASE_ARCH = os.path.join(GAME, r"archive\pc\content\lang_en_text.archive")
EN_EP1_ARCH  = os.path.join(GAME, r"archive\pc\ep1\lang_en_text.archive")

QUEUE_OUT   = os.path.join(SCRIPTS_DIR, "missing_translations_queue.json")
REPORT_OUT  = os.path.join(SCRIPTS_DIR, "audit_missing_report.txt")

# CDPR-internal QA report (not user-facing text) + voiceovermaps (binary
# audio cues with NUL bytes — not translatable).
SKIP_SECTIONS = {"stringidvariantlengthsreport.json"}
SKIP_PREFIXES = ("voiceovermap",)

WOLVENKIT_TIMEOUT = 600


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def index_by_pk(entries):
    """Build {str(pk): entry} from a list of localization entries."""
    out = {}
    for e in entries:
        pk = e.get("primaryKey")
        if pk is None:
            continue
        out[str(pk)] = e
    return out


def is_empty(entry):
    fem = (entry.get("femaleVariant") or "").strip()
    mal = (entry.get("maleVariant") or "").strip()
    return not fem and not mal


def is_present_and_nonempty(entry):
    return entry is not None and not is_empty(entry)


def section_excluded(section: str) -> bool:
    if section in SKIP_SECTIONS:
        return True
    base = section.split("/")[-1]
    return any(base.startswith(p) for p in SKIP_PREFIXES)


def run_cli(args, timeout=WOLVENKIT_TIMEOUT):
    try:
        r = subprocess.run(
            [CLI] + args,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout,
        )
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return False, f"EXCEPTION: {e}"


def extract_and_serialize_onscreens(archive_path: str, label: str) -> dict:
    """Extract onscreens.json + onscreens_final.json from a game archive,
    serialize to text JSON, return {section_key: [entries]} merged.

    section_key normalized to 'onscreens/<filename>' so it matches the
    export schema.
    """
    if not os.path.exists(archive_path):
        log(f"  [skip] archive missing: {archive_path}")
        return {}

    work = os.path.join(TRUTH_CACHE, label)
    raw_dir = os.path.join(work, "raw")
    json_dir = os.path.join(work, "json")
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    Path(json_dir).mkdir(parents=True, exist_ok=True)

    cached_json = list(Path(json_dir).glob("onscreens*.json.json"))
    if len(cached_json) >= 2:
        log(f"  [cache hit] {label}: reusing {len(cached_json)} serialized files")
    else:
        log(f"  extracting from {os.path.basename(archive_path)} (label={label})")
        for pattern in ("*onscreens.json*", "*onscreens_final.json*"):
            ok, out = run_cli(
                ["extract", archive_path, "-o", raw_dir, "-w", pattern]
            )
            if not ok:
                log(f"    extract failed for {pattern}: {out[-200:]}")
                return {}
        # Locate the two extracted CR2W files and serialize each to JSON.
        for cr2w in Path(raw_dir).rglob("onscreens*.json"):
            ok, out = run_cli(["convert", "serialize", str(cr2w), "-o", json_dir])
            if not ok:
                log(f"    serialize failed for {cr2w.name}: {out[-200:]}")
                return {}
        cached_json = list(Path(json_dir).glob("onscreens*.json.json"))
        log(f"  serialized {len(cached_json)} files to {json_dir}")

    result = {}
    for js in cached_json:
        with open(js, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = data["Data"]["RootChunk"]["root"]["Data"]["entries"]
        # filename is e.g. 'onscreens.json.json' -> section key 'onscreens/onscreens.json'
        section_filename = js.name[: -len(".json")]  # drop the WolvenKit '.json' suffix
        section_key = f"onscreens/{section_filename}"
        result[section_key] = entries
        log(f"    {section_key}: {len(entries):,} entries")
    return result


def build_truth(refresh: bool = False) -> dict:
    """Union of (export from project) + (live extracts from game archives).
    Live extracts WIN for sections they cover — they're the authoritative
    engine-visible truth.

    Returns {section_key: [entries]} ready for cross-reference.
    """
    log("loading user-curated export (truth seed)…")
    with open(EXPORT, "r", encoding="utf-8") as f:
        export = json.load(f)
    log(f"  export sections: {len(export):,}")

    if refresh and os.path.exists(TRUTH_CACHE):
        log(f"--refresh: clearing {TRUTH_CACHE}")
        shutil.rmtree(TRUTH_CACHE, ignore_errors=True)
    Path(TRUTH_CACHE).mkdir(parents=True, exist_ok=True)

    log("extracting live truth from game archives…")
    live = {}
    for arch, label in [
        (EN_BASE_ARCH, "base"),
        (EN_EP1_ARCH, "ep1"),
    ]:
        extract_and_serialize_onscreens_into(arch, label, live)

    if not live:
        log("WARN: no live extracts produced. Using export alone.")
        return export

    log("merging live extracts over export…")
    merged = dict(export)
    for section_key, entries in live.items():
        before = len(merged.get(section_key, []))
        # Union: live is authoritative for keys it covers, but we keep
        # any entries that only the export knows about (defensive) and
        # also append any entries unique to other live archives later.
        # Done via primaryKey-indexed dict so each pk appears once.
        union = index_by_pk(merged.get(section_key, []))
        for e in entries:
            pk = e.get("primaryKey")
            if pk is None:
                continue
            # live entry wins on conflict (engine truth > stale export)
            union[str(pk)] = e
        merged[section_key] = list(union.values())
        log(f"  {section_key}: export={before:,} -> union={len(merged[section_key]):,}  "
            f"(Δ {len(merged[section_key]) - before:+,})")
    return merged


def extract_and_serialize_onscreens_into(archive_path: str, label: str,
                                          accumulator: dict) -> None:
    """Like extract_and_serialize_onscreens but accumulates entries into
    `accumulator[section_key]` (union by primaryKey) so base+ep1 merge."""
    section_results = extract_and_serialize_onscreens(archive_path, label)
    for section_key, entries in section_results.items():
        existing = accumulator.get(section_key, [])
        union = index_by_pk(existing)
        for e in entries:
            pk = e.get("primaryKey")
            if pk is None:
                continue
            union[str(pk)] = e
        accumulator[section_key] = list(union.values())


def main():
    t0 = time.time()

    refresh = "--refresh" in sys.argv

    truth = build_truth(refresh=refresh)
    log(f"truth sections after augmentation: {len(truth):,}")

    log("loading current translations (HE)…")
    with open(TRANSLATED, "r", encoding="utf-8") as f:
        translated = json.load(f)
    log(f"  sections: {len(translated):,}")

    # Per-section missing accumulator
    missing_by_section = {}        # section -> [ {pk, sk, english_fem, english_mal} ]
    section_stats = []              # (section, total_en, missing_count)

    grand_total_en = 0
    grand_total_missing = 0

    for section, en_entries in truth.items():
        en_idx = index_by_pk(en_entries)
        # Only count EN entries that have something to translate.
        en_with_text = {pk: e for pk, e in en_idx.items()
                        if is_present_and_nonempty(e)}
        grand_total_en += len(en_with_text)

        if section_excluded(section):
            section_stats.append((section, len(en_with_text), -1))  # -1 = skipped
            continue

        he_idx = index_by_pk(translated.get(section, []))

        missing = []
        for pk, en_entry in en_with_text.items():
            he_entry = he_idx.get(pk)
            if he_entry is None or is_empty(he_entry):
                missing.append({
                    "primaryKey":     en_entry["primaryKey"],
                    "secondaryKey":   en_entry.get("secondaryKey", "") or "",
                    "english_female": en_entry.get("femaleVariant", "") or "",
                    "english_male":   en_entry.get("maleVariant", "") or "",
                })

        if missing:
            missing_by_section[section] = missing
        grand_total_missing += len(missing)
        section_stats.append((section, len(en_with_text), len(missing)))

    elapsed = time.time() - t0
    log(f"audit done in {elapsed:.1f}s")
    log(f"  total EN strings:                {grand_total_en:,}")
    log(f"  total MISSING in HE translation: {grand_total_missing:,}")
    log(f"  sections with at least 1 gap:    {len(missing_by_section):,}")

    # ── Write queue file (ready for LM Studio batch) ────────────────────
    queue = {
        "_metadata": {
            "generated_at":         time.strftime("%Y-%m-%d %H:%M:%S"),
            "source_export":        EXPORT,
            "source_live_truth":    [EN_BASE_ARCH, EN_EP1_ARCH],
            "source_translated":    TRANSLATED,
            "total_en_strings":     grand_total_en,
            "total_missing":        grand_total_missing,
            "sections_with_gaps":   len(missing_by_section),
            "skipped_sections":     sorted(SKIP_SECTIONS),
            "skipped_prefixes":     list(SKIP_PREFIXES),
        },
        "missing": missing_by_section,
    }
    with open(QUEUE_OUT, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)
    log(f"queue written -> {QUEUE_OUT}  ({os.path.getsize(QUEUE_OUT):,} bytes)")

    # ── Write human-readable report ────────────────────────────────────
    # Category buckets: onscreens / subtitles / other
    buckets = Counter()
    bucket_missing = Counter()
    for section, total_en, missing_count in section_stats:
        if section.startswith("onscreens/"):
            bucket = "onscreens"
        elif section.startswith("subtitles/"):
            bucket = "subtitles"
        elif missing_count == -1:
            bucket = "skipped (CDPR internal QA)"
        else:
            bucket = "other"
        buckets[bucket] += total_en
        if missing_count > 0:
            bucket_missing[bucket] += missing_count

    # Subtitle sub-buckets (quest vs voicesets vs scenes vs …)
    sub_sub = Counter()
    sub_sub_missing = Counter()
    for section, total_en, missing_count in section_stats:
        if not section.startswith("subtitles/"):
            continue
        parts = section.split("/")
        sub = parts[1] if len(parts) > 1 else "(top)"  # subtitles/<sub>/...
        sub_sub[sub] += total_en
        if missing_count > 0:
            sub_sub_missing[sub] += missing_count

    # Top-30 sections by missing count
    section_stats_sorted = sorted(
        (s for s in section_stats if s[2] > 0),
        key=lambda s: -s[2],
    )

    lines = []
    lines.append("=" * 78)
    lines.append("CYBERPUNK 2077 HEBREW TRANSLATION — MISSING-STRING AUDIT")
    lines.append(f"generated {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 78)
    lines.append("")
    lines.append(f"Source export:      {EXPORT}")
    lines.append(f"Translated state:   {TRANSLATED}")
    lines.append(f"Audit elapsed:      {elapsed:.1f}s")
    lines.append("")
    lines.append("─" * 78)
    lines.append("TOTALS")
    lines.append("─" * 78)
    lines.append(f"  Total EN strings (across all categories):  {grand_total_en:>10,}")
    lines.append(f"  Already translated (or otherwise present):  "
                 f"{grand_total_en - grand_total_missing:>10,}")
    lines.append(f"  MISSING from HE translation:               "
                 f"{grand_total_missing:>10,}")
    pct = 100.0 * grand_total_missing / max(1, grand_total_en)
    lines.append(f"  Missing share:                              {pct:>9.1f}%")
    lines.append("")
    lines.append(f"  Sections with at least one gap:            "
                 f"{len(missing_by_section):>10,}")
    lines.append("")
    lines.append("─" * 78)
    lines.append("BY HIGH-LEVEL CATEGORY")
    lines.append("─" * 78)
    for bucket, total in sorted(buckets.items(), key=lambda x: -x[1]):
        miss = bucket_missing.get(bucket, 0)
        pct = 100.0 * miss / max(1, total)
        lines.append(f"  {bucket:<30s}  total={total:>8,}  "
                     f"missing={miss:>8,}  ({pct:>5.1f}%)")
    lines.append("")
    lines.append("─" * 78)
    lines.append("SUBTITLES BREAKDOWN (sub-folder under subtitles/)")
    lines.append("─" * 78)
    for sub, total in sorted(sub_sub.items(), key=lambda x: -x[1]):
        miss = sub_sub_missing.get(sub, 0)
        pct = 100.0 * miss / max(1, total)
        lines.append(f"  subtitles/{sub:<25s}  total={total:>8,}  "
                     f"missing={miss:>8,}  ({pct:>5.1f}%)")
    lines.append("")
    lines.append("─" * 78)
    lines.append("TOP 30 SECTIONS BY MISSING COUNT")
    lines.append("─" * 78)
    for section, total_en, miss in section_stats_sorted[:30]:
        pct = 100.0 * miss / max(1, total_en)
        lines.append(f"  {section:<60s}  {miss:>6,} / {total_en:>6,}  ({pct:>5.1f}%)")
    lines.append("")
    lines.append("─" * 78)
    lines.append("ALL SECTIONS WITH GAPS (full list)")
    lines.append("─" * 78)
    for section, total_en, miss in section_stats_sorted:
        lines.append(f"  {section:<70s}  {miss:>6,}")
    lines.append("")
    lines.append("=" * 78)
    lines.append("END OF REPORT")
    lines.append("=" * 78)

    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    log(f"report written -> {REPORT_OUT}  ({os.path.getsize(REPORT_OUT):,} bytes)")

    # Echo a tight summary to stdout
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total EN strings:           {grand_total_en:>9,}")
    print(f"  MISSING in HE translation:  {grand_total_missing:>9,}")
    print(f"  Sections with gaps:         {len(missing_by_section):>9,}")
    print()
    print("By category:")
    for bucket, total in sorted(buckets.items(), key=lambda x: -x[1]):
        miss = bucket_missing.get(bucket, 0)
        print(f"  {bucket:<30s}  missing {miss:>6,} / {total:>6,}")
    print()
    print(f"Queue file:  {QUEUE_OUT}")
    print(f"Report file: {REPORT_OUT}")


if __name__ == "__main__":
    main()
