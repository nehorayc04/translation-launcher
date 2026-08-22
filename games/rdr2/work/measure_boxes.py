#!/usr/bin/env python3
"""measure_boxes.py — how wide is each text box, measured from the game's own shipped line breaks.

WHY THIS EXISTS. The engine wraps in STORAGE order and our Hebrew is stored VISUAL, so any value
the engine has to wrap itself comes out with its LINE ORDER INVERTED — the sentence starts on the
bottom line and climbs. The only defence is to pre-wrap with explicit `~n~`, which the engine
honours (proven in-game, proof #3). That needs the box width, and the build was using 110 chars —
the width of the boot SPLASH, the widest surface in the game — so almost nothing was pre-wrapped
and almost everything inverted.

TWO INDEPENDENT ORACLES, no game launch, and they agree:
  * Rockstar's OWN English, wherever it carries an authored `~n~`  -> median box 36 chars
  * Ko Games' Arabic mod (a SHIPPING RTL translation on this exact engine, which hit this exact
    problem and hand-wrapped 1,173 strings)                        -> median box 37 chars

ESTIMATOR: the MAX segment of a wrapped value, not the median of all segments. A greedy wrap
leaves every line just under the box except the LAST one, so averaging over all segments is
dragged down by short last-lines; the widest line of one value is the closest thing to the box.

Output `box_widths.json` = {family: visible-char budget} + a default. Families with too little
evidence fall back to the default, and everything is clamped so one odd family cannot produce
absurd fragmentation.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import build_ct_strings as B  # noqa: E402
import rdr2_text as R         # noqa: E402

EN = os.path.join(HERE, "..", "extract", "game_text", "american.json")
OUT = os.path.join(HERE, "box_widths.json")

# Both oracles put the median box at 36-37 visible chars. 40 leaves a little slack for a surface
# neither oracle happened to wrap, and the cost asymmetry is stark: too NARROW is a slightly
# taller block of text, too WIDE is an inverted, unreadable paragraph.
DEFAULT = 40
CLAMP_LO, CLAMP_HI = 28, 60
MIN_EVIDENCE = 6
PARAGRAPH = 90            # a segment longer than this is a paragraph separator, not a wrap

TOK = re.compile(r"~[^~]*~")
FAM = re.compile(r"^([A-Z]{2,}[0-9]*)_")


def visible(s: str) -> int:
    """Width in characters the player actually sees; a token draws a glyph, not its own name."""
    return len(TOK.sub("  ", s).strip())


def family(key: str) -> str:
    if key.startswith("0x"):
        return "<hash>"
    m = FAM.match(key)
    return m.group(1) if m else key.split("_")[0][:12]


def max_segments(book: dict) -> dict:
    """{family: [max-segment width, ...]} over values that were genuinely WRAPPED."""
    out = defaultdict(list)
    for k, v in book.items():
        if not isinstance(v, str) or "~n~" not in v:
            continue
        segs = [visible(s) for s in v.split("~n~") if visible(s)]
        if len(segs) < 2 or max(segs) > PARAGRAPH:
            continue
        out[family(k)].append(max(segs))
    return out


def main() -> None:
    english = json.load(open(EN, encoding="utf-8"))
    arabic = R.to_map(R.parse(open(B.KO_GXT, encoding="utf-8").read()))

    fe, fa = max_segments(english), max_segments(arabic)
    table, skipped = {}, 0
    for fam in set(fe) | set(fa):
        ev = sorted(fe.get(fam, []) + fa.get(fam, []))
        if len(ev) < MIN_EVIDENCE:
            skipped += 1
            continue
        med = ev[len(ev) // 2]
        table[fam] = max(CLAMP_LO, min(CLAMP_HI, med))

    allev = sorted(w for L in list(fe.values()) + list(fa.values()) for w in L)
    print(f"evidence: english {sum(map(len, fe.values())):,} values, "
          f"arabic {sum(map(len, fa.values())):,} values")
    print(f"global median box: {allev[len(allev)//2]} visible chars  "
          f"(default in use: {DEFAULT})")
    print(f"families with a measured box: {len(table)}   (too little evidence: {skipped})\n")
    for f, w in sorted(table.items(), key=lambda x: x[1]):
        n = len(fe.get(f, [])) + len(fa.get(f, []))
        print(f"   {f:<16} {w:>3} chars   (n={n})")

    json.dump({"default": DEFAULT, "families": table}, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, sort_keys=True)
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
