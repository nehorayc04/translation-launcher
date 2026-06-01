"""Purge foreign-script-contaminated translations and queue them for retranslation.

Re-runs the same script detection logic as audit_translations.py (foreign
chars OUTSIDE markup tags — `<kiroshi l="jpn" o="…">` audio cues stay
intact). For every contaminated femaleVariant / maleVariant:

  1. Wipe the field in localization_translated.json (set to "").
  2. Drop matching tm_cache.json entries so the Phase-2 TM pass doesn't
     instantly re-populate the same bad value.
  3. Append the entry (with original English from localization_export.json)
     to cleanup_queue.json so translate_cleanup_all.py picks it up.

Run only when no translator process is alive — it edits files the
translator writes back periodically.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import time
from collections import defaultdict

# Force UTF-8 stdout/stderr so non-ASCII characters in log lines don't
# crash the script on a cp1255/cp1252 Windows console.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", write_through=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", write_through=True)

SCRIPTS_DIR  = r"C:\Users\Nehoray_Cohen\Projects\Game translator"
RESOURCES    = os.path.join(SCRIPTS_DIR, "תרגום_משחקים", "source", "resources")

TRANSLATED   = os.path.join(RESOURCES, "localization_translated.json")
ENGLISH      = os.path.join(RESOURCES, "localization_export.json")
TM_CACHE     = os.path.join(RESOURCES, "tm_cache.json")
QUEUE_FILE   = os.path.join(SCRIPTS_DIR, "cleanup_queue.json")

# ── Detection (mirrors audit_translations.py) ────────────────────────────
SCRIPT_RANGES = {
    "cyrillic":            (0x0400, 0x04FF),
    "cyrillic_supplement": (0x0500, 0x052F),
    "arabic":              (0x0600, 0x06FF),
    "arabic_supplement":   (0x0750, 0x077F),
    "arabic_extended_a":   (0x08A0, 0x08FF),
    "thai":                (0x0E00, 0x0E7F),
    "greek":               (0x0370, 0x03FF),
    "armenian":            (0x0530, 0x058F),
    "devanagari":          (0x0900, 0x097F),
    "han_cjk":             (0x4E00, 0x9FFF),
    "hiragana":            (0x3040, 0x309F),
    "katakana":            (0x30A0, 0x30FF),
    "hangul":              (0xAC00, 0xD7AF),
    "ethiopic":            (0x1200, 0x137F),
    "georgian":            (0x10A0, 0x10FF),
}
NIQQUD_RANGE = (0x0591, 0x05C7)
_TAG_RE = re.compile(r"<[^<>]*>|\{[^{}]*\}")


def is_contaminated(text: str) -> bool:
    if not text:
        return False
    stripped = _TAG_RE.sub(" ", text)
    for ch in stripped:
        cp = ord(ch)
        for lo, hi in SCRIPT_RANGES.values():
            if lo <= cp <= hi:
                return True
        if NIQQUD_RANGE[0] <= cp <= NIQQUD_RANGE[1]:
            return True
    return False


def atomic_write(path: str, data) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def main() -> int:
    # ── 0. Sanity backups ────────────────────────────────────────────────
    stamp = time.strftime("%Y%m%d_%H%M%S")
    for src in (TRANSLATED, TM_CACHE, QUEUE_FILE):
        if os.path.exists(src):
            bak = f"{src}.bak.purge.{stamp}"
            with open(src, "rb") as fin, open(bak, "wb") as fout:
                fout.write(fin.read())
            print(f"[bak] {os.path.basename(bak)}")

    # ── 1. Load everything ───────────────────────────────────────────────
    print(f"[*] Loading {TRANSLATED}")
    with open(TRANSLATED, "r", encoding="utf-8") as f:
        translated = json.load(f)

    print(f"[*] Loading {ENGLISH}")
    with open(ENGLISH, "r", encoding="utf-8") as f:
        english = json.load(f)
    english_index: dict[tuple[str, str], dict] = {}
    for section, rows in english.items():
        if not isinstance(rows, list):
            continue
        for e in rows:
            if isinstance(e, dict) and e.get("primaryKey") is not None:
                english_index[(section, str(e["primaryKey"]))] = e

    tm_cache: dict[str, str] = {}
    if os.path.exists(TM_CACHE):
        try:
            with open(TM_CACHE, "r", encoding="utf-8") as f:
                tm_cache = json.load(f)
            if not isinstance(tm_cache, dict):
                tm_cache = {}
        except json.JSONDecodeError:
            tm_cache = {}

    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            queue_payload = json.load(f)
    else:
        queue_payload = {"_metadata": {}, "queue": []}
    queue_items = queue_payload.get("queue", [])
    already_queued: set[tuple[str, str]] = {
        (it["section"], str(it["primaryKey"])) for it in queue_items
    }

    # ── 2. Scan + wipe in-memory ─────────────────────────────────────────
    per_section_purged: dict[str, int] = defaultdict(int)
    appended_to_queue   = 0
    skipped_no_english  = 0
    already_in_queue    = 0
    total_purged_fields = 0
    new_queue_entries: list[dict] = []

    for section, rows in translated.items():
        if not isinstance(rows, list):
            continue
        for entry in rows:
            if not isinstance(entry, dict):
                continue
            pk = entry.get("primaryKey")
            pk_str = str(pk) if pk is not None else None
            skey   = entry.get("secondaryKey") or ""

            wiped_any = False
            for field in ("femaleVariant", "maleVariant"):
                val = entry.get(field) or ""
                if val and is_contaminated(val):
                    entry[field] = ""
                    per_section_purged[section] += 1
                    total_purged_fields += 1
                    wiped_any = True

            if not wiped_any or pk_str is None:
                continue

            key = (section, pk_str)
            if key in already_queued:
                already_in_queue += 1
                continue

            en = english_index.get(key)
            if not en:
                skipped_no_english += 1
                continue
            efv = (en.get("femaleVariant") or "").strip()
            emv = (en.get("maleVariant")   or "").strip()
            if not efv and not emv:
                skipped_no_english += 1
                continue
            new_queue_entries.append({
                "section":        section,
                "primaryKey":     pk_str,
                "secondaryKey":   skey,
                "english_female": efv,
                "english_male":   emv,
            })
            already_queued.add(key)
            appended_to_queue += 1

    # ── 3. Purge tm_cache entries that still hold bad Hebrew ─────────────
    tm_before = len(tm_cache)
    tm_cache  = {k: v for k, v in tm_cache.items() if not is_contaminated(v)}
    tm_dropped = tm_before - len(tm_cache)

    # ── 4. Update queue payload + persist ────────────────────────────────
    queue_items.extend(new_queue_entries)
    queue_payload["queue"] = queue_items
    md = queue_payload.setdefault("_metadata", {})
    md.update({
        "purge_run_at":       time.strftime("%Y-%m-%d %H:%M:%S"),
        "purge_appended":     appended_to_queue,
        "purge_total_fields": total_purged_fields,
        "total_items":        len(queue_items),
    })

    atomic_write(TRANSLATED, translated)
    atomic_write(TM_CACHE,   tm_cache)
    atomic_write(QUEUE_FILE, queue_payload)

    # ── 5. Report ────────────────────────────────────────────────────────
    print()
    print(f"[*] Wiped {total_purged_fields:,} contaminated variants "
          f"across {len(per_section_purged):,} sections")
    print(f"[*] Dropped {tm_dropped:,} tm_cache entries that held bad Hebrew "
          f"(was {tm_before:,} → now {len(tm_cache):,})")
    print(f"[*] Appended {appended_to_queue:,} entries to cleanup_queue.json")
    if already_in_queue:
        print(f"      ({already_in_queue:,} were already queued — left alone)")
    if skipped_no_english:
        print(f"      ({skipped_no_english:,} skipped — no English source in "
              f"localization_export.json)")
    print(f"[*] cleanup_queue.json now holds {len(queue_items):,} items")
    print()
    print("Top affected sections (purged variants):")
    for sect, n in sorted(per_section_purged.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {n:>5,}  {sect}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
