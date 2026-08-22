"""Build the community `/translate` pool payload for Borderless Gaming.

Two surfaces, one pool:
  * the app INTERFACE   -> hebrew.json, keyed by the flattened dotted path
  * the EFFECT EDITOR   -> effects_he/<table>.json, keyed by the ENGLISH string

`string_key` therefore carries its target table as a prefix, so an approved
export maps straight back onto the right file with no guessing:

    ui:App.Title
    fx.categories:Film      fx.names:Blur Fill      fx.labels:Sharpness
    fx.descriptions:...     fx.tooltips:...

`section` is the HEBREW category (the DB trigger passes a Hebrew section
through to `category` verbatim), ordered by VISIBILITY so a partial pass
covers what users actually see first  [[community-pool-by-category]].

`current_he` is seeded with the value the BUILD emits - never a raw
accumulator - so a contributor reviews the text the app really renders.

    python work/build_ct_strings.py            # report + write extract/ct_upload.json
    python universal/community_translate.py import borderless-gaming <that file>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / "extract" / "ct_upload.json"

# table -> (corpus kind in effects_en.json, hebrew category, order block)
FX = {
    "categories":   ("CATEGORY",    "שמות אפקטים וקטגוריות"),
    "names":        ("EFFECT",      "שמות אפקטים וקטגוריות"),
    "labels":       ("PARAM_LABEL", "הגדרות אפקטים"),
    "descriptions": ("DESCRIPTION", "תיאורים והסברים"),
    "tooltips":     ("PARAM_DESC",  "תיאורים והסברים"),
}

# visibility order - the app UI first, then what you see opening an effect
SECTIONS = [
    "ממשק ותפריטים",
    "שמות אפקטים וקטגוריות",
    "הגדרות אפקטים",
    "תיאורים והסברים",
]

LETTER = re.compile(r"[A-Za-z֐-׿]")
# pure codes/ids that are never translated (and must not invite a "fix")
CODE_KEYS = {"Language.Code"}
# corpus entries that are metadata placeholders, not user-visible text
FX_JUNK = {"Category", "desc", "..."}


def translatable(key: str, en: str) -> bool:
    if key in CODE_KEYS:
        return False
    if en in FX_JUNK:
        return False
    return bool(LETTER.search(en))


def main() -> int:
    en_ui = json.loads((HERE / "extract" / "en.json").read_text("utf-8"))
    he_ui = json.loads((HERE / "hebrew.json").read_text("utf-8"))
    fx_en = json.loads((HERE / "extract" / "effects_en.json").read_text("utf-8"))

    rows: list[dict] = []
    dropped: list[str] = []

    # ── 1. the app interface ────────────────────────────────────────────
    for key, en in en_ui.items():
        if not translatable(key, en):
            dropped.append(f"ui:{key} = {en!r}")
            continue
        rows.append({
            "string_key": f"ui:{key}",
            "source_en": en,
            "current_he": he_ui.get(key, ""),
            "section": "ממשק ותפריטים",
            "context": f"מפתח בקובץ השפה: {key}",
        })

    # ── 2. the effect editor ────────────────────────────────────────────
    for table, (kind, section) in FX.items():
        he = json.loads((HERE / "effects_he" / f"{table}.json").read_text("utf-8"))
        for en, sources in fx_en[kind].items():
            if not translatable("", en):
                dropped.append(f"fx.{table}: {en!r}")
                continue
            cur = he.get(en, "")
            if not cur:
                # no Hebrew = a brand / algorithm name that stays Latin on
                # purpose (Anime4K, AMD CAS, FSR ...). Uploading it blank would
                # ask contributors to translate a product name.
                dropped.append(f"fx.{table}: {en!r} (נשאר באנגלית בכוונה)")
                continue
            first = sources[0] if sources else ""
            eff = Path(first).stem.replace(".slang", "") if first else ""
            extra = f" (+{len(sources) - 1})" if len(sources) > 1 else ""
            rows.append({
                "string_key": f"fx.{table}:{en}",
                "source_en": en,
                "current_he": cur,
                "section": section,
                "context": f"עורך האפקטים · {eff}{extra}" if eff else "עורך האפקטים",
            })

    # ── order by visibility, contiguous blocks ──────────────────────────
    rows.sort(key=lambda r: (SECTIONS.index(r["section"]), r["string_key"]))
    for i, r in enumerate(rows):
        r["order_index"] = i

    seen: dict[str, int] = {}
    for r in rows:
        seen[r["string_key"]] = seen.get(r["string_key"], 0) + 1
    dupes = {k: n for k, n in seen.items() if n > 1}
    assert not dupes, f"duplicate string_key: {list(dupes)[:5]}"
    longest = max(len(r["string_key"].encode()) for r in rows)
    assert longest < 2400, f"string_key too long for the btree index: {longest} B"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(rows)} rows -> {OUT}")
    for s in SECTIONS:
        n = sum(1 for r in rows if r["section"] == s)
        seeded = sum(1 for r in rows if r["section"] == s and r["current_he"])
        print(f"  {s:24s} {n:4d}   (מתורגם כבר: {seeded})")
    print(f"longest string_key: {longest} B")
    print(f"\ndropped {len(dropped)} (not translatable / deliberately Latin):")
    for d in dropped[:8]:
        print("  -", d)
    if len(dropped) > 8:
        print(f"  ... +{len(dropped) - 8}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
