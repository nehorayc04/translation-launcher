#!/usr/bin/env python3
"""build_yesno_probe.py — a LADDER that names the key drawing the alert's Yes/No row.

WHY A LADDER AND NOT ANOTHER GUESS. I inferred the row came from `0xE234DD49`
(`~INPUT_FRONTEND_ACCEPT~ Yes ~INPUT_FRONTEND_CANCEL~ No`), fixed a real bug in the leading-token
rule that mangles that string, shipped it — and the buttons are still gone. So the inference was
wrong (or incomplete) and inference is the wrong instrument. Several keys can render the same row
and there is no way to know a-priori which one the engine reads ([[measure-with-a-ladder]]).

EVERY candidate gets its OWN pure-Latin marker, so ONE launch answers three questions at once:
  * a marker APPEARS      -> that key IS the row, and the row renders fine with Latin ⇒ the bug
                             is Hebrew-specific (bidi/width/glyph), not "the row is disabled"
  * NOTHING appears       -> no text key drives it ⇒ the cause is NOT the text at all, and the
                             next single-variable test is the FONT
  * the marker is Latin   -> font-independent and bidi-independent by construction, so neither
                             can mask the answer ([[proof-marker-must-be-meaningless-to-engine]])

    python build_yesno_probe.py --deploy     # ladder build
    python build_yesno_probe.py --revert     # back to the normal build
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "gtav", "work"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from gtav_gxt2 import joaat            # noqa: E402
import rdr2_text as R                  # noqa: E402

GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2"
GXT2 = os.path.join(GAME, "lml", "tranar", "Ko Games Studio.gxt2")
AM = os.path.join(HERE, "..", "extract", "game_text_v2", "american.json")

FRONT = re.compile(r"~INPUT_FRONTEND_(?:ACCEPT|CANCEL)~")


def candidates() -> dict[str, str]:
    """Prompt-SHAPED keys only. A broad 'contains Yes/No' sweep returns 2,424 keys because item
    names carry 'No.' -- that would overwrite half the shop with markers and prove nothing."""
    am = json.load(open(AM, encoding="utf-8"))
    recs = R.parse(open(GXT2, encoding="utf-8").read())
    h2k = {}
    for r in recs:
        if r["kind"] != "entry":
            continue
        k = r["key"]
        h2k[(k if k.startswith("0x") else f"0x{joaat(k):08X}").upper()] = k

    out = {}
    for h, e in am.items():
        if not isinstance(e, str):
            continue
        s = e.strip()
        # ⚠️ the length cap must clear the COMBINED row: `~INPUT_FRONTEND_ACCEPT~ Yes
        # ~INPUT_FRONTEND_CANCEL~ No` is 52 chars, and a 44-char cap silently dropped the single
        # most likely candidate from the ladder.
        keep = (s in ("Yes", "No", "YES", "NO")) or (len(s) <= 80 and FRONT.search(s))
        if not keep:
            continue
        k = h2k.get(h.upper())
        if k:
            out[k] = s
    return out


def markers(cands: dict[str, str]) -> dict[str, str]:
    """One distinct, pronounceable Latin tag per key so the screenshot names the winner."""
    out, ny, nn, na = {}, 0, 0, 0
    for k, e in sorted(cands.items(), key=lambda x: (x[1], x[0])):
        s = e.strip()
        if s in ("Yes", "YES"):
            ny += 1
            out[k] = f"ZY{ny:02d}"
        elif s in ("No", "NO"):
            nn += 1
            out[k] = f"ZN{nn:02d}"
        else:
            na += 1
            # keep the engine tokens so the row still has its glyphs to draw
            body = FRONT.sub(lambda m: m.group(0), s)
            toks = re.findall(r"~[^~]*~", body)
            out[k] = "".join(toks) + f"ZA{na:02d}"
    return out


def main() -> None:
    cands = candidates()
    marks = markers(cands)
    print(f"candidates: {len(cands)}")
    for k, m in sorted(marks.items(), key=lambda x: x[1]):
        print(f"   {m:<28} <- {k:<32} {cands[k]!r}")

    if "--deploy" not in sys.argv and "--revert" not in sys.argv:
        print("\n(dry run — pass --deploy or --revert)")
        return

    env = dict(os.environ)
    if "--deploy" in sys.argv:
        path = os.path.join(HERE, "_yesno_probe.json")
        json.dump(marks, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        env["RDR2_OVERRIDE_JSON"] = path
        print(f"\n-> {path} ({len(marks)} markers)")

    print("\nbuilding ...", flush=True)
    r = subprocess.run([sys.executable, "-u", os.path.join(HERE, "build_full.py"), "--deploy"],
                       cwd=HERE, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print(r.stdout[-1200:] or r.stderr[-1200:])


if __name__ == "__main__":
    main()
