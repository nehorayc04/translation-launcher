# -*- coding: utf-8 -*-
"""98_anchor_subtitle_punct.py — bake per-segment trailing &rlm; into the SUBTITLE +
DIALOGUE spine so Hebrew sentence-final punctuation (? ! . : … ; , --) renders on the
LEFT (RTL end) instead of flipping to the right. Mirrors the game's official Arabic
anchoring, adapted for Hebrew's NEUTRAL `?` (Arabic's `؟` is strong-RTL and needs no
anchor — which is exactly why the Gemini pass left `?`-endings unanchored).

Idempotent (skips already-anchored segments) + backs up each file. Run from work/
BEFORE the 10→15→80 rebuild (step 10 reads subtitles_he.json + dialogue_he.json).
"""
import json, os, re, shutil, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "universal")))
from rtl_anchor import anchor_value, TS_SPLIT  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ["subtitles_he.json", "dialogue_he.json"]
DRY = "--dry" in sys.argv


def count_unanchored(d):
    """How many <ts> segments end in neutral terminal punct WITHOUT an anchor."""
    n = 0
    for v in d.values():
        if not isinstance(v, str) or "<span" in v:
            continue
        for p in TS_SPLIT.split(v)[::2]:
            if anchor_value("<ts=\"x\">" + p) != "<ts=\"x\">" + p:
                n += 1
    return n


def main():
    total_entries = total_changed = 0
    for fn in FILES:
        path = os.path.join(HERE, fn)
        if not os.path.exists(path):
            print(f"  (skip) {fn} not found")
            continue
        d = json.load(open(path, encoding="utf-8"))
        before = count_unanchored(d)
        changed = 0
        samples = []
        nd = {}
        for k, v in d.items():
            nv = anchor_value(v) if isinstance(v, str) else v
            if nv != v:
                changed += 1
                if len(samples) < 4:
                    samples.append((k, v[:70], nv[:80]))
            nd[k] = nv
        print(f"== {fn}: {len(d)} entries  |  unanchored-punct segments: {before}  |  entries changed: {changed}")
        for k, o, n in samples:
            print(f"   {k}\n     OLD {o}\n     NEW {n}")
        total_entries += len(d); total_changed += changed
        if not DRY and changed:
            shutil.copyfile(path, path + ".bak_punct")
            tmp = path + ".tmp"
            json.dump(nd, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            os.replace(tmp, path)
            print(f"   WRITTEN (backup {fn}.bak_punct)")
    print(f"\n{'DRY-RUN (nothing written)' if DRY else 'DONE'} — {total_changed} entries anchored across {len(FILES)} files")


if __name__ == "__main__":
    main()
