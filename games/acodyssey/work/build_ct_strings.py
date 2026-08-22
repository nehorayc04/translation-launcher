#!/usr/bin/env python3
r"""
build_ct_strings.py — build the `/translate` community-pool upload for AC Odyssey.

Source = `DataPC_patch_01.forge` (the copy that SHADOWS the base) —
`LocalizationPackage_English` + `_English_Subtitles`.

Decisions baked in, each measured rather than assumed:

* **`string_key` carries its TARGET SURFACE** — `ui:<id>` / `subs:<id>`. The two id
  spaces are disjoint (0 overlap), but the prefix says which LocalizationPackage an
  approved line goes back into, so an export drops onto the build with no remapping.
* **NO dedup by the English string.** 1,763 duplicate-English groups exist, and the
  game's OWN professional locales give them different translations at
  ru 36.7 % · de 37.2 % · fr 34.0 % · it 20.6 % · pl 12.7 % · ar 10.6 % · es 10.0 %.
  Seven independent locales agree a third are context-dependent → key by id
  ([[dedup-safety-from-game-langs]]).
* **Categories are ordered by VISIBILITY** ([[community-pool-by-category]]) and come
  from the engine's OWN surface metadata (the package a string lives in), never a
  length heuristic: `ממשק ותפריטים` (UI) → `כתוביות עלילה` (subtitles).
* **Every row carries the game's own ARABIC in `context`** as the gender source
  ([[gender-oracle-from-game-langs]]) — Arabic is the Semitic near-match Hebrew
  wants, it ships at 100 % id parity, and it is stored LOGICAL with 0 presentation
  forms so it is readable as-is. A RUSSIAN line is appended where present, because
  Russian past tense marks speaker AND addressee gender, which English drops.
  Only the RAW sentences are shipped — no auto-derived hint, because Odyssey's
  Arabic is largely unvocalized and an open-class guess manufactures confident
  garbage ([[gender-hint-needs-closed-set]]).
* **Dropped rows are evidence-based:** a line is dropped only when NO real letter
  survives after the engine tokens are stripped (pure tokens / numbers / symbols).
  A bare proper noun stays — a name passthrough is a TRANSLATOR decision.
  ⚠️ `[sigh]` / `[&gasp]` / `[Save Icon]` are PROSE here, not tokens (the shipped
  Arabic translates them), so they must NOT be stripped when testing for content.

    python work/build_ct_strings.py            # -> extract/ct_upload.json + report
"""
import argparse
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "..", "acunity", "work"))

import aco_forge                                        # noqa: E402
import aco_cfd                                          # noqa: E402
import aco_loc                                          # noqa: E402
import aco_rtl                                          # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GAME = os.environ.get("ACO_GAME", r"F:\Games\Assassin's Creed Odyssey")
PATCH = os.path.join(GAME, "DataPC_patch_01.forge")
GAME_ID = "acodyssey"                     # == the existing Supabase games.id

CAT_UI = "ממשק ותפריטים"
CAT_SUBS = "כתוביות עלילה"

SRC = [
    ("ui", "LocalizationPackage_English", CAT_UI),
    ("subs", "LocalizationPackage_English_Subtitles", CAT_SUBS),
]
ORACLE = [
    ("ar", "LocalizationPackage_Arabic", "LocalizationPackage_Arabic_Subtitles"),
    ("ru", "LocalizationPackage_Russian", "LocalizationPackage_Russian_Subtitles"),
]

# Only the ENGINE tokens are stripped when asking "is there content here?".
# aco_rtl.TOKEN already excludes prose brackets like [sigh] / [&gasp].
LETTER = re.compile(r"[A-Za-z\u0590-\u05FF\u0600-\u06FF]")


def has_content(s):
    """A row is worth translating if a real letter survives token removal."""
    return bool(LETTER.search(aco_rtl.TOKEN.sub(" ", s or "")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "extract", "ct_upload.json"))
    a = ap.parse_args()

    fg = aco_forge.Forge(PATCH)
    od = aco_cfd.oodle()

    en = {}
    for tag, pkg, cat in SRC:
        en[tag] = aco_loc.find(fg, pkg, od).strings()
        print(f"  {pkg:<42} {len(en[tag]):>7,}")

    oracle = {}
    for code, ui_pkg, subs_pkg in ORACLE:
        oracle[code] = {
            "ui": aco_loc.find(fg, ui_pkg, od).strings(),
            "subs": aco_loc.find(fg, subs_pkg, od).strings(),
        }
        print(f"  oracle {code}: ui {len(oracle[code]['ui']):,} "
              f"subs {len(oracle[code]['subs']):,}")
    fg.close()

    rows, dropped = [], collections.Counter()
    order = 0
    for tag, pkg, cat in SRC:
        # stable, reproducible ordering inside each visibility block
        for sid in sorted(en[tag], key=lambda x: int(x)):
            text = en[tag][sid]
            if not has_content(text):
                dropped[cat] += 1
                continue
            ctx = []
            ar = oracle["ar"][tag].get(sid)
            ru = oracle["ru"][tag].get(sid)
            if ar:
                ctx.append(f"ערבית: {ar}")
            if ru:
                ctx.append(f"רוסית: {ru}")
            rows.append({
                "string_key": f"{tag}:{sid}",
                "source_en": text,
                "current_he": "",
                "context": " · ".join(ctx),
                "section": cat,
                "order_index": order,
            })
            order += 1

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(rows, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)

    by_cat = collections.Counter(r["section"] for r in rows)
    with_ar = sum(1 for r in rows if "ערבית:" in r["context"])
    with_ru = sum(1 for r in rows if "רוסית:" in r["context"])
    print()
    for cat in (CAT_UI, CAT_SUBS):
        print(f"  {cat:<20} {by_cat[cat]:>7,}   (dropped {dropped[cat]:,})")
    print(f"  {'TOTAL':<20} {len(rows):>7,}   (dropped {sum(dropped.values()):,})")
    print(f"  gender source: Arabic on {with_ar:,}  Russian on {with_ru:,}")
    print(f"\nwrote {a.out}")

    # A round-trip guard: every key must resolve back onto a real build target.
    # ⚠️ payload keys are INTS — compare with int(sid), not the string from the
    # key ([[json-roundtrip-hides-key-type]]). A str compare flags 100 % as bad,
    # which looks like catastrophic data loss and is purely the guard's own bug.
    bad = []
    for r in rows:
        tag, sid = r["string_key"].split(":", 1)
        k = int(sid)
        if k not in en[tag] or en[tag][k] != r["source_en"]:
            bad.append(r["string_key"])
    print(f"round-trip check: {len(bad)} unresolvable / mismatched keys")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
