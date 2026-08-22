#!/usr/bin/env python3
"""build_hebrew.py - build the Hebrew gxt2 layer for GTA V **Enhanced**.

The translation corpus is keyed by the **English source string**, not by a hash or a
file name, so it is entirely independent of Enhanced's own key set. That is what makes
the Legacy -> Enhanced port cheap: every English line Enhanced shares with Legacy gets
its Hebrew automatically, and any Enhanced-only line simply stays English - a clean,
readable fallback rather than a blank.

  !! Never ship Legacy's built gxt2 files as-is. A gxt2 REPLACES the whole table, so an
     Enhanced-only key that is missing from Legacy's file would render EMPTY in-game.
     Always rebuild on top of *Enhanced's own* vanilla tables, which is what this does.

Inputs
  extract/vanilla/<tag>/<...>american_rel.rpf/*.gxt2   Enhanced vanilla (extract_vanilla.py)
  games/gtav/agent_handoff_full/{reuse_he,hebrew*}.json  the EN->HE corpus (~141k)

Output
  build/<tag>/<nested>/*.gxt2      Hebrew, VISUAL-ordered, byte-faithful
  build/coverage.json              per-file coverage + every Enhanced-only English string

    python work/build_hebrew.py
    python work/build_hebrew.py --report-only     # coverage without writing gxt2
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
REPO = os.path.normpath(os.path.join(ROOT, "..", ".."))
LEGACY_WORK = os.path.join(REPO, "games", "gtav", "work")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, LEGACY_WORK)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import gxt2 as G                                    # noqa: E402  our copy of the codec
import gtav_rtl                                     # noqa: E402  the REAL UBA transform
# strip_gloss / _toks / load_translations are imported rather than duplicated so the
# Enhanced build can never drift from the Legacy one.
from build_full_gxt2 import strip_gloss, _toks, load_translations, HEB   # noqa: E402

EXTRACT = os.path.join(ROOT, "extract", "vanilla")
BUILD = os.path.join(ROOT, "build")


def find_tables():
    """[(tag, relative_dir, [gxt2 paths])] for every extracted vanilla table."""
    out = []
    if not os.path.isdir(EXTRACT):
        return out
    for tag in sorted(os.listdir(EXTRACT)):
        tdir = os.path.join(EXTRACT, tag)
        if not os.path.isdir(tdir):
            continue
        for nested in sorted(os.listdir(tdir)):
            ndir = os.path.join(tdir, nested)
            if not os.path.isdir(ndir):
                continue
            files = sorted(f for f in os.listdir(ndir) if f.lower().endswith(".gxt2"))
            if files:
                out.append((tag, nested, ndir, files))
    return out


def main():
    global EXTRACT, BUILD
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--extract", default=EXTRACT,
                    help="vanilla-extract dir (override to validate against another install)")
    ap.add_argument("--build", default=BUILD)
    a = ap.parse_args()
    EXTRACT, BUILD = os.path.abspath(a.extract), os.path.abspath(a.build)

    tables = find_tables()
    if not tables:
        print("NO VANILLA EXTRACT - run work/extract_vanilla.py first.")
        print("It needs the OpenIV-decrypted mods\\ folder; see PIPELINE.md 'bootstrap'.")
        return 2

    tr = load_translations()
    tot_e = tot_he = tot_en = 0
    missing = {}                      # Enhanced English with no Hebrew -> occurrence count
    deviations = []                   # token-multiset drift, same guard as Legacy
    per_file = []

    for tag, nested, ndir, files in tables:
        outdir = os.path.join(BUILD, tag, nested)
        if not a.report_only:
            os.makedirs(outdir, exist_ok=True)
        for fn in files:
            src = G.read_gxt2(open(os.path.join(ndir, fn), "rb").read())
            out, f_he, f_en = {}, 0, 0
            for h, en in src.items():
                he = tr.get(en)
                if he is not None:
                    if _toks(he) != _toks(en):
                        deviations.append({"file": fn, "en": en, "he": he})
                    out[h] = gtav_rtl.to_visual(strip_gloss(he, en))
                    f_he += 1
                else:
                    out[h] = en                       # English fallback, never blank
                    if HEB.search(en):
                        f_he += 1                     # already-Hebrew shared string
                    else:
                        f_en += 1
                        if en.strip():
                            missing[en] = missing.get(en, 0) + 1
            if not a.report_only:
                data = G.write_gxt2(out)
                assert G.read_gxt2(data) == out, fn   # round-trip guard
                with open(os.path.join(outdir, fn), "wb") as fh:
                    fh.write(data)
            tot_e += len(src)
            tot_he += f_he
            tot_en += f_en
            per_file.append({"tag": tag, "nested": nested, "file": fn,
                             "entries": len(src), "hebrew": f_he, "english": f_en})

    pct = 100.0 * tot_he / tot_e if tot_e else 0.0
    print(f"tables  : {len(tables)}  files={sum(len(t[3]) for t in tables)}")
    print(f"entries : {tot_e:,}")
    print(f"hebrew  : {tot_he:,}  ({pct:.1f}%)")
    print(f"english : {tot_en:,}  fallback (Enhanced-only or untranslated)")
    print(f"distinct untranslated English strings: {len(missing):,}")
    if deviations:
        print(f"token deviations: {len({d['en'] for d in deviations}):,} distinct (review)")

    os.makedirs(BUILD, exist_ok=True)
    with open(os.path.join(BUILD, "coverage.json"), "w", encoding="utf-8") as fh:
        json.dump({"entries": tot_e, "hebrew": tot_he, "english": tot_en,
                   "pct": round(pct, 2), "per_file": per_file,
                   "missing_english": sorted(missing.items(), key=lambda kv: -kv[1])},
                  fh, ensure_ascii=False, indent=1)
    print(f"-> {os.path.relpath(BUILD, ROOT)}/coverage.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
