#!/usr/bin/env python3
r"""
build_ct_strings.py — build the community `/translate` pool upload for UNCHARTED LoT.

Same engine family as TLOU1, same contract ([[community-pool-by-category]] + CLAUDE.md §17):
  * read the 3 ND string tables from the PRISTINE `text2.psarc` (`.he_backup` if a proof is
    deployed, else the live archive),
  * global-dedup by EN (many sids share one EN; the build applies Hebrew by EN → all sids),
  * `string_key = md5(EN)[:16]` — byte-identical to the future to_translate.json, so an approved
    export drops straight onto the build,
  * `section` = the Hebrew VISIBILITY category, ordered so the most-seen text is served first,
  * `current_he = ''` (fresh game).

    python build_ct_strings.py            -> extract/ct_upload.json (+ report)
"""
import os
import sys
import json
import hashlib
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "tlou1", "tools"))
sys.path.insert(0, os.path.join(ROOT, "games", "uncharted_lot", "tools"))

GAME = os.environ.get("UNC_GAME", r"F:\Game Lab\UNCHARTED - Legacy of Thieves Collection")
os.environ.setdefault("TLOU_OODLE_DLL", os.path.join(GAME, "oo2core_9_win64.dll"))
PC = os.path.join(GAME, "Uncharted4_data", "build", "pc")
OUT = os.path.join(HERE, "..", "extract")

from psarc import Psarc               # noqa: E402
import unc_loc                        # noqa: E402

# Hebrew categories in VISIBILITY order — the most-seen text finishes first.
CAT = [("eng.common", "ממשק ותפריטים"),
       ("eng.subtitles", "כתוביות עלילה"),
       ("eng.subtitles-systemic", "דיבורי רקע")]


def is_translatable(en):
    """Drop pure number/symbol/token rows — a name/code passthrough is a translator decision."""
    if not en or not en.strip():
        return False
    return any(c.isalpha() for c in en)


def key(en):
    return hashlib.md5(en.encode("utf-8")).hexdigest()[:16]


def _src_archive():
    a = os.path.join(PC, "uncharted4", "text2.psarc")
    return a + ".he_backup" if os.path.exists(a + ".he_backup") else a


def main():
    arc = _src_archive()
    print(f"source: {os.path.relpath(arc, GAME)}")
    p = Psarc(arc)

    def table(suffix):
        e = [x for x in p.files() if x.path.endswith(suffix)][0]
        return unc_loc.to_map(p.extract(e))

    seen = {}          # md5key -> row (first-seen category wins = visibility order)
    order = 0
    stats = {}
    for suffix, cat in CAT:
        m = table(suffix)
        added = 0
        for en in m.values():
            if not is_translatable(en):
                continue
            k = key(en)
            if k in seen:
                continue
            seen[k] = {"string_key": k, "source_en": en, "current_he": "",
                       "context": "", "section": cat, "order_index": order}
            order += 1
            added += 1
        stats[cat] = (len(m), added)

    rows = list(seen.values())
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "ct_upload.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)

    print(f"\n=== ct_upload.json : {len(rows):,} unique translatable rows ===")
    for suffix, cat in CAT:
        recs, uniq = stats[cat]
        print(f"  {cat:22s} {uniq:>7,} unique  (of {recs:,} records)")
    ln = [len(r["source_en"]) for r in rows]
    print(f"  chars {sum(ln):,}  median {sorted(ln)[len(ln)//2]}  max {max(ln):,}")
    tok = sum(1 for r in rows if re.search(r"\[[^\]]+\]", r["source_en"]))
    print(f"  [TOKEN] rows {tok}")
    print(f"\nnext: python universal/community_translate.py import uncharted "
          f"games/uncharted_lot/extract/ct_upload.json")


if __name__ == "__main__":
    main()
