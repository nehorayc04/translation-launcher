#!/usr/bin/env python3
r"""
build_ct_strings.py — build the `/translate` community-pool upload for AC Origins.

Sources = BOTH `DataPC.forge` (base game) AND `DataPC_22_dlc_patch_01.forge` (the
one paid DLC bundle) — `LocalizationPackage_English` + `_English_Subtitles` on the
base, `DLC22-30_LocalizationPackage_English(US)` + `_Subtitles` on the DLC.

Decisions baked in, each measured rather than assumed:

* **The DLC's English package was previously INVISIBLE to `scope_report.py`** —
  its name suffix is `English(US)`, not `English`, so the LANGS lookup silently
  skipped it and the game's own scope report undercounted by ~2,900 real lines.
  This script reads it by its EXACT name instead of a language-suffix lookup.
* **`string_key` carries its TARGET SURFACE** — `ui:<id>` / `subs:<id>` — no
  base/dlc prefix needed: MEASURED 0 id overlap between base and DLC in both
  directions and both kinds (base ui ids 287,239–60,000,220; dlc ui ids
  4,000,003–4,011,389 — disjoint ranges), so one key scheme covers both sources.
* **NO dedup by the English string.** 368 UI + 288 subtitle duplicate-English
  groups exist in the base alone, and the game's OWN professional locales give
  them different translations (subs: ru 44.7% · fr 38.8% · de 36.5% · pl 32.2% ·
  ar 28.6% diverge). Key by id ([[dedup-safety-from-game-langs]]).
* **Categories ordered by VISIBILITY** ([[community-pool-by-category]]), from the
  engine's OWN Type field, never a length heuristic: `ממשק ותפריטים` (UI, base
  then DLC) → `כתוביות עלילה` (subtitles, base then DLC).
* **Gender source = the game's own Arabic + Russian + Polish** in `context`
  ([[gender-oracle-from-game-langs]]) — Arabic is the Semitic near-match and
  ships at 100% UI parity but only 86.9% subtitle parity (base); Russian marks
  speaker AND addressee gender via past tense; Polish likewise via `-ł/-ła`.
  Only the RAW sentences are shipped, no auto-derived hint — Origins's Arabic
  is largely unvocalized ([[gender-hint-needs-closed-set]]).
* **Dropped rows are evidence-based:** a line is dropped only when no real
  letter survives after the ENGINE tokens are stripped (pure tokens / numbers /
  symbols). `aor_rtl.TOKEN` already excludes prose brackets like `[sigh]`
  (Origins overloads `[...]`, see the `[[proof-marker-must-be-meaningless-to-engine]]`
  trap in PIPELINE.md #5) — a bare proper noun stays, that's a translator call.

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

import aor_forge                                        # noqa: E402
import aor_cfd                                          # noqa: E402
import aor_loc                                          # noqa: E402
import aor_rtl                                           # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GAME = os.environ.get("AOR_GAME", r"F:\Games\Assassin's Creed Origins")
GAME_ID = "acorigins"                     # == the existing Supabase games.id

CAT_UI = "ממשק ותפריטים"
CAT_SUBS = "כתוביות עלילה"

# (src label, forge relative path, ui pkg name, subs pkg name, category)
SRC = [
    ("base", "DataPC.forge",
     "LocalizationPackage_English", "LocalizationPackage_English_Subtitles"),
    ("dlc", "DataPC_22_dlc_patch_01.forge",
     "DLC22-30_LocalizationPackage_English(US)",
     "DLC22-30_LocalizationPackage_English(US)_Subtitles"),
]
# (lang code, base ui, base subs, dlc ui, dlc subs)
ORACLE = [
    ("ar", "ערבית", "LocalizationPackage_Arabic", "LocalizationPackage_Arabic_Subtitles",
     "DLC22-30_LocalizationPackage_Arabic", "DLC22-30_LocalizationPackage_Arabic_Subtitles"),
    ("ru", "רוסית", "LocalizationPackage_Russian", "LocalizationPackage_Russian_Subtitles",
     "DLC22-30_LocalizationPackage_Russian", "DLC22-30_LocalizationPackage_Russian_Subtitles"),
    ("pl", "פולנית", "LocalizationPackage_Polish", "LocalizationPackage_Polish_Subtitles",
     "DLC22-30_LocalizationPackage_Polish", "DLC22-30_LocalizationPackage_Polish_Subtitles"),
]

# Only the ENGINE tokens are stripped when asking "is there content here?".
# aor_rtl.TOKEN already excludes prose brackets like [sigh] / [&gasp].
LETTER = re.compile(r"[A-Za-z\u0590-\u05FF\u0600-\u06FF]")


def has_content(s):
    """A row is worth translating if a real letter survives token removal."""
    return bool(LETTER.search(aor_rtl.TOKEN.sub(" ", s or "")))


def load_pkg(fg, od, name):
    try:
        return aor_loc.find(fg, name, od).strings()
    except KeyError:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "extract", "ct_upload.json"))
    a = ap.parse_args()

    forges = {}
    en = {}          # (src, kind) -> {id:text}
    oracle = {}       # (code, src, kind) -> {id:text}

    for src, rel, ui_pkg, subs_pkg in SRC:
        path = os.path.join(GAME, rel)
        fg = aor_forge.Forge(path)
        forges[src] = fg
        od = aor_cfd.oodle()

        en[(src, "ui")] = load_pkg(fg, od, ui_pkg)
        en[(src, "subs")] = load_pkg(fg, od, subs_pkg)
        print(f"  {src:5s} ui   {ui_pkg:<55} {len(en[(src,'ui')]):>7,}")
        print(f"  {src:5s} subs {subs_pkg:<55} {len(en[(src,'subs')]):>7,}")

    for code, _label, b_ui, b_subs, d_ui, d_subs in ORACLE:
        od = aor_cfd.oodle()
        oracle[(code, "base", "ui")] = load_pkg(forges["base"], od, b_ui)
        oracle[(code, "base", "subs")] = load_pkg(forges["base"], od, b_subs)
        oracle[(code, "dlc", "ui")] = load_pkg(forges["dlc"], od, d_ui)
        oracle[(code, "dlc", "subs")] = load_pkg(forges["dlc"], od, d_subs)
        print(f"  oracle {code}: base-ui {len(oracle[(code,'base','ui')]):,} "
              f"base-subs {len(oracle[(code,'base','subs')]):,} "
              f"dlc-ui {len(oracle[(code,'dlc','ui')]):,} "
              f"dlc-subs {len(oracle[(code,'dlc','subs')]):,}")

    for fg in forges.values():
        fg.close()

    rows, dropped = [], collections.Counter()
    order = 0
    for kind, cat in (("ui", CAT_UI), ("subs", CAT_SUBS)):
        for src, _rel, _ui, _subs in SRC:
            table = en[(src, kind)]
            for sid in sorted(table, key=lambda x: int(x)):
                text = table[sid]
                if not has_content(text):
                    dropped[cat] += 1
                    continue
                ctx = []
                for code, label, *_ in ORACLE:
                    v = oracle[(code, src, kind)].get(sid)
                    if v:
                        ctx.append(f"{label}: {v}")
                rows.append({
                    "string_key": f"{kind}:{sid}",
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
    with_pl = sum(1 for r in rows if "פולנית:" in r["context"])
    print()
    for cat in (CAT_UI, CAT_SUBS):
        print(f"  {cat:<20} {by_cat[cat]:>7,}   (dropped {dropped[cat]:,})")
    print(f"  {'TOTAL':<20} {len(rows):>7,}   (dropped {sum(dropped.values()):,})")
    print(f"  gender source: Arabic {with_ar:,}  Russian {with_ru:,}  Polish {with_pl:,}")
    print(f"\nwrote {a.out}")

    # A round-trip guard: every key must resolve back onto a real build target.
    # ⚠️ payload keys are INTS — compare with int(sid), not the string from the
    # key ([[json-roundtrip-hides-key-type]]).
    bad = []
    keyed = {}
    for kind, _cat in (("ui", None), ("subs", None)):
        merged = {}
        for src, _rel, _ui, _subs in SRC:
            merged.update(en[(src, kind)])
        keyed[kind] = merged
    for r in rows:
        kind, sid = r["string_key"].split(":", 1)
        k = int(sid)
        if k not in keyed[kind] or keyed[kind][k] != r["source_en"]:
            bad.append(r["string_key"])
    print(f"round-trip check: {len(bad)} unresolvable / mismatched keys")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
