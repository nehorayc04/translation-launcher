"""
verify_translation.py
---------------------
Audits the Cyberpunk 2077 Hebrew localization files.

Checks:
  1. Total entries (original vs translated, should match)
  2. Hebrew count
  3. Skip list count
  4. Missing translations (English sentences left behind, not in skip list, not UI bindings)
  5. Tag integrity (UI tags preserved between original and translation)
"""

import json
import os
import re
import sys

# Force UTF-8 output so Hebrew samples don't crash the console
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = r"C:\Users\Nehoray_Cohen\Projects\Game translator\תרגום_משחקים\source\resources"
ORIGINAL_FILE = os.path.join(BASE, "localization_export.json")
TRANSLATED_FILE = os.path.join(BASE, "localization_translated.json")
SKIP_FILE = os.path.join(BASE, "translation_skips.json")

ALLOWED_FOLDERS = ["onscreens", "subtitles"]
FIELDS = ("femaleVariant", "maleVariant")

TAG_RE = re.compile(r"<[^>]+>|\{[^}]+\}|%[a-zA-Z]")
HEBREW_RE = re.compile(r"[֐-׿]")
LATIN_RE = re.compile(r"[A-Za-z]")


def in_allowed_folder(path):
    return any(f in path.lower() for f in ALLOWED_FOLDERS)


def has_hebrew(text):
    return bool(HEBREW_RE.search(text)) if isinstance(text, str) else False


def is_ui_binding(text):
    """A UI binding is a short string with <=1 English letter (e.g. '+W', 'Q', '[')."""
    if not isinstance(text, str) or not text.strip():
        return True
    cleaned = re.sub(r"<[^>]+>", "", text)
    letters = re.sub(r"[^a-zA-Z]", "", cleaned)
    return len(letters) <= 1


def load_json(path, label):
    if not os.path.exists(path):
        print(f"  [!] Missing file: {path}")
        return None
    size_mb = os.path.getsize(path) / 1_048_576
    print(f"  Loading {label} ({size_mb:.1f} MB)...", end="", flush=True)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        print(f" {len(data):,} entries")
    else:
        print(f" {len(data):,} files")
    return data


def fmt(n):
    return f"{n:,}"


def line(label, value, width=48):
    dots = "." * max(2, width - len(label) - len(str(value)))
    print(f"  {label} {dots} {value}")


def section(title):
    print("\n" + "=" * 64)
    print(f"  {title}")
    print("=" * 64)


def main():
    print("\n" + "=" * 64)
    print("  CYBERPUNK 2077 — Hebrew Translation Verification Report")
    print("=" * 64 + "\n")

    print("  [*] Loading source files...")
    original = load_json(ORIGINAL_FILE, "localization_export.json")
    translated = load_json(TRANSLATED_FILE, "localization_translated.json")
    skips_raw = load_json(SKIP_FILE, "translation_skips.json")

    if original is None or translated is None:
        print("\n  [!] Cannot continue without source + translated files.")
        sys.exit(1)

    skips = set()
    if skips_raw:
        skips = set(tuple(x) for x in skips_raw)

    # ── Counters ───────────────────────────────────────────────
    total_orig = 0
    total_trans = 0
    file_count_orig = 0
    file_count_trans = 0
    hebrew_count = 0
    skipped_in_list = 0
    ui_bindings = 0
    missing = 0
    missing_samples = []
    broken_tags = 0
    broken_tag_samples = []
    empty_orig = 0

    for filepath, orig_entries in original.items():
        if not in_allowed_folder(filepath):
            continue

        file_count_orig += 1
        trans_entries = translated.get(filepath, [])
        if filepath in translated:
            file_count_trans += 1

        for i, orig in enumerate(orig_entries):
            t = trans_entries[i] if i < len(trans_entries) else {}
            if not isinstance(t, dict):
                t = {}

            for field in FIELDS:
                ov = orig.get(field, "")
                tv = t.get(field, "")

                total_orig += 1
                if isinstance(tv, str) and tv.strip():
                    total_trans += 1

                if not isinstance(ov, str) or not ov.strip():
                    empty_orig += 1
                    continue

                # Skip-list check
                in_skip = (filepath, str(i), field) in skips

                if has_hebrew(tv):
                    hebrew_count += 1
                    # Tag integrity check (only on entries that got translated)
                    orig_tags = TAG_RE.findall(ov)
                    if orig_tags:
                        for tag in orig_tags:
                            if tag not in tv:
                                broken_tags += 1
                                if len(broken_tag_samples) < 5:
                                    broken_tag_samples.append(
                                        (filepath, i, field, tag, ov[:50], tv[:50])
                                    )
                                break
                    continue

                # No Hebrew at this point
                if in_skip:
                    skipped_in_list += 1
                    continue

                if is_ui_binding(ov):
                    ui_bindings += 1
                    continue

                # Real English sentence not skipped and not translated
                missing += 1
                if len(missing_samples) < 10:
                    missing_samples.append((filepath, i, field, ov[:60], tv[:60]))

    # ── Report ─────────────────────────────────────────────────
    section("1. FILE COUNTS (onscreens + subtitles only)")
    line("Files in original (allowed folders)", fmt(file_count_orig))
    line("Files in translated (allowed folders)", fmt(file_count_trans))
    match_files = "[OK] MATCH" if file_count_orig == file_count_trans else "[FAIL] MISMATCH"
    line("File count match", match_files)

    section("2. ENTRY COUNTS")
    line("Total fields in original", fmt(total_orig))
    line("Total fields with content in translated", fmt(total_trans))
    line("Empty original fields (skipped from analysis)", fmt(empty_orig))

    section("3. TRANSLATION STATUS")
    actionable = total_orig - empty_orig - ui_bindings
    line("Entries WITH Hebrew text", fmt(hebrew_count))
    line("UI bindings (no translation needed)", fmt(ui_bindings))
    line("Skipped (in translation_skips.json)", fmt(skipped_in_list))
    line("MISSING (English left behind, not skipped)", fmt(missing))
    print()

    if actionable > 0:
        pct_done = 100 * hebrew_count / actionable
        line("Coverage of actionable entries", f"{pct_done:.2f}%")

    section("4. TAG INTEGRITY")
    line("Translated entries with broken tags", fmt(broken_tags))
    if broken_tag_samples:
        print("\n  Examples of broken tags:")
        for fp, i, field, tag, ov, tv in broken_tag_samples:
            short_fp = fp.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
            print(f"    [{short_fp}#{i}.{field}] missing tag '{tag}'")
            print(f"      orig:  {ov!r}")
            print(f"      trans: {tv!r}")

    section("5. MISSING TRANSLATIONS (samples)")
    if missing == 0:
        print("\n  [OK] No missing translations — all actionable entries are either")
        print("    translated or explicitly skipped.")
    else:
        print(f"\n  [!] {missing} entries have no Hebrew and are not in the skip list.")
        print(f"  Showing first {len(missing_samples)}:\n")
        for fp, i, field, ov, tv in missing_samples:
            short_fp = fp.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
            print(f"    [{short_fp}#{i}.{field}]")
            print(f"      orig:  {ov!r}")
            print(f"      trans: {tv!r}")

    # ── Final verdict ─────────────────────────────────────────
    section("FINAL VERDICT")
    issues = []
    if file_count_orig != file_count_trans:
        issues.append(f"file count mismatch ({file_count_orig} vs {file_count_trans})")
    if missing > 0:
        issues.append(f"{missing} missing translations")
    if broken_tags > 0:
        issues.append(f"{broken_tags} entries with broken tags")

    if not issues:
        print("\n  [OK] ALL CHECKS PASSED — translation looks complete and tag-safe.\n")
    else:
        print("\n  [!] Issues detected:")
        for issue in issues:
            print(f"    - {issue}")
        print()


if __name__ == "__main__":
    main()
