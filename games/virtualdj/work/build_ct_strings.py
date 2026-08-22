r"""Build the community /translate upload for VirtualDJ.

string_key = the flat "Section/Key" (identical to agent_handoff/hebrew.json keys), so an
approved export drops straight back into work/build_final.py with zero remapping.
current_he = the CLEAN LOGICAL Hebrew (the RLE bidi wrap is applied at BUILD time, never stored).
Categories are Hebrew and ordered by VISIBILITY (what a user sees first).

  python build_ct_strings.py    ->  extract/ct_strings.json
"""
import sys, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(GAME / "tools"))
import vdj_lang as V

# section -> (hebrew category, visibility rank)
CAT = {
    "Skin": ("ממשק ותפריטים", 0), "skin_deprecated": ("ממשק ותפריטים", 0),
    "RootElements": ("ממשק ותפריטים", 0), "Columns": ("ממשק ותפריטים", 0),
    "ContextMenu": ("ממשק ותפריטים", 0), "DragDrop": ("ממשק ותפריטים", 0),
    "Colors": ("ממשק ותפריטים", 0), "AudioSource": ("ממשק ותפריטים", 0),
    "EffectRoot": ("ממשק ותפריטים", 0), "Search": ("ממשק ותפריטים", 0),
    "Config": ("הודעות וטקסטים", 1), "Messages": ("הודעות וטקסטים", 1),
    "Errors": ("הודעות וטקסטים", 1),
    "Settings": ("הגדרות", 2),
    "Plugins": ("אפקטים ותוספים", 3),
    "tooltips": ("טולטיפים", 4), "skintooltips": ("טולטיפים", 4),
    "Actions": ("פקודות VDJScript", 5),
}
WORD = re.compile(r"[A-Za-z]{2,}")


def main():
    en_attrib, en_secs = V.parse((GAME / "extract" / "langs_orig" / "English.xml").read_bytes())
    en = dict(V.flatten(en_secs))
    he = json.load(open(GAME / "agent_handoff" / "hebrew.json", encoding="utf-8"))
    rows, dropped = [], 0
    for key, src in en.items():
        sec = key.split("/")[0]
        cat, rank = CAT.get(sec, ("אחר", 9))
        s = (src or "").strip()
        if not WORD.search(s) and not re.search(r"[0-9]", s):
            dropped += 1          # pure symbols / empty -> nothing to translate
            continue
        rows.append({
            "string_key": key,
            "source_en": src,
            "current_he": he.get(key, ""),
            "section": cat,
            "context": key,
            "order_index": rank,
        })
    # contiguous order_index per category, in visibility order
    rows.sort(key=lambda r: (r["order_index"], r["string_key"]))
    for i, r in enumerate(rows):
        r["order_index"] = i
    out = GAME / "extract" / "ct_strings.json"
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    from collections import Counter
    c = Counter(r["section"] for r in rows)
    print(f"wrote {out}  rows={len(rows)}  dropped={dropped}")
    for cat, _rank in sorted({v: k for k, v in CAT.values()}.items()):
        pass
    for cat, n in sorted(c.items(), key=lambda kv: min(r["order_index"] for r in rows if r["section"] == kv[0])):
        have = sum(1 for r in rows if r["section"] == cat and r["current_he"].strip())
        print(f"  {cat:22} {n:5}   (with Hebrew {have})")


if __name__ == "__main__":
    main()
