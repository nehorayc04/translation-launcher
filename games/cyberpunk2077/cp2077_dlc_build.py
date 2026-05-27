"""
cp2077_dlc_build.py
===================
Builds dlc_ep1_translated.json — the Hebrew working file for the Phantom
Liberty DLC, the ep1 analog of localization_translated.json.

Source: dlc_ep1_text.json (English DLC text, built by cp2077_consolidate_dlc.py
— 716 sections / ~47,905 entries: 2 onscreens + 714 subtitle files).

The output mirrors dlc_ep1_text.json exactly (same sections, same entries,
same keys) — femaleVariant / maleVariant start as the English source and are
either:
  * pre-filled with Hebrew REUSED from the base translation when the exact
    English string was already translated for the base game (zero LM cost), or
  * left as English — the DLC translator (cp2077_dlc_translate.py) will
    overwrite them. An entry still holding its English value == untranslated.

Base reuse index — English -> Hebrew, from localization_translated.json:
  * onscreens: English comes from localization_export.json (by section+pk),
    Hebrew from the translated file.
  * subtitles: English is the entry's own secondaryKey, Hebrew the femaleVariant.

Re-runnable. Does NOT overwrite an existing dlc_ep1_translated.json that
already has translation progress unless --force is given (so a half-done
translation is never wiped).

Run: python cp2077_dlc_build.py [--force]
"""
from __future__ import annotations

import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))

_REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))   # games/<game>/ -> repo root
RES = os.path.join(_REPO_ROOT, "תרגום_משחקים", "source", "resources")

DLC_TEXT       = os.path.join(RES, "dlc_ep1_text.json")
DLC_TRANSLATED = os.path.join(RES, "dlc_ep1_translated.json")
BASE_TR        = os.path.join(RES, "localization_translated.json")
BASE_EX        = os.path.join(RES, "localization_export.json")

HEB    = re.compile(r"[֐-׿]")
LETTER = re.compile(r"[A-Za-z]")
MARKUP = ("<kiroshi", "<mothertongue", "<Rich")
ONSCREENS = ("onscreens/onscreens.json", "onscreens/onscreens_final.json")


def is_markup(v: str) -> bool:
    return bool(v) and any(m in v for m in MARKUP)


def build_reuse_index(base_tr: dict, base_ex: dict) -> dict:
    """English -> Hebrew, harvested from the finished base translation."""
    reuse: dict[str, str] = {}
    # onscreens — English via the export, by (section, pk)
    ex_on: dict = {}
    for sec in ONSCREENS:
        for e in base_ex.get(sec, []):
            if isinstance(e, dict) and e.get("primaryKey") is not None:
                ex_on[(sec, str(e["primaryKey"]))] = e
    for sec in ONSCREENS:
        for e in base_tr.get(sec, []):
            if not isinstance(e, dict) or e.get("primaryKey") is None:
                continue
            ex_e = ex_on.get((sec, str(e["primaryKey"])))
            if not ex_e:
                continue
            for fld in ("femaleVariant", "maleVariant"):
                en = ex_e.get(fld) or ""
                he = e.get(fld) or ""
                if en and LETTER.search(en) and HEB.search(he):
                    reuse.setdefault(en, he)
    # subtitles — English IS the entry's own secondaryKey
    for sec, rows in base_tr.items():
        if not sec.startswith("subtitles/") or not isinstance(rows, list):
            continue
        for e in rows:
            if not isinstance(e, dict):
                continue
            en = e.get("secondaryKey") or ""
            he = e.get("femaleVariant") or ""
            if en and LETTER.search(en) and HEB.search(he):
                reuse.setdefault(en, he)
    return reuse


def main() -> int:
    force = "--force" in sys.argv
    for p in (DLC_TEXT, BASE_TR, BASE_EX):
        if not os.path.exists(p):
            sys.exit(f"FATAL: missing {p}")

    if os.path.exists(DLC_TRANSLATED) and not force:
        # Guard: never wipe a translation already in progress.
        cur = json.load(open(DLC_TRANSLATED, encoding="utf-8"))
        heb = sum(1 for rows in cur.values() if isinstance(rows, list)
                  for e in rows if isinstance(e, dict)
                  and HEB.search(e.get("femaleVariant") or ""))
        sys.exit(f"dlc_ep1_translated.json already exists ({heb:,} entries carry "
                 f"Hebrew). Re-run with --force to rebuild from scratch.")

    print("loading dlc_ep1_text.json …")
    dlc = json.load(open(DLC_TEXT, encoding="utf-8"))
    print("loading localization_translated.json …")
    base_tr = json.load(open(BASE_TR, encoding="utf-8"))
    print("loading localization_export.json …")
    base_ex = json.load(open(BASE_EX, encoding="utf-8"))

    print("building base reuse index …")
    reuse = build_reuse_index(base_tr, base_ex)
    print(f"  base English->Hebrew pairs: {len(reuse):,}")

    out: dict = {}
    reused = lm_plain = lm_markup = trivial = 0
    for sec, rows in dlc.items():
        if not isinstance(rows, list):
            out[sec] = rows
            continue
        new_rows = []
        for e in rows:
            if not isinstance(e, dict):
                new_rows.append(e)
                continue
            ne = dict(e)
            for fld in ("femaleVariant", "maleVariant"):
                v = e.get(fld) or ""
                if not v:
                    continue
                if not LETTER.search(v):
                    trivial += 1                       # code / number — leave
                    continue
                if v in reuse:
                    ne[fld] = reuse[v]
                    reused += 1
                elif is_markup(v):
                    lm_markup += 1                     # left English -> markup LM
                else:
                    lm_plain += 1                      # left English -> plain LM
            new_rows.append(ne)
        out[sec] = new_rows

    with open(DLC_TRANSLATED, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print()
    print(f"  reused from base (zero LM):   {reused:,}")
    print(f"  need LM — plain:              {lm_plain:,}")
    print(f"  need LM — markup:             {lm_markup:,}")
    print(f"  trivial (code/number, kept):  {trivial:,}")
    print(f"  TOTAL LM workload:            {lm_plain + lm_markup:,}")
    print(f"\n-> {DLC_TRANSLATED} ({os.path.getsize(DLC_TRANSLATED):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
