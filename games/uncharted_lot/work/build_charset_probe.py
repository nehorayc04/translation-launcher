#!/usr/bin/env python3
r"""
build_charset_probe.py — PROOF #5: FINGERPRINT the active font instead of guessing it.

Four font sources have now been patched and ruled out in-game:
    main.fnt bitmap atlas · fontlib.iggy (6 fonts) · fontlib.swf (5) ·
    fontlib-universal.swf (4) · controller-movie.iggy
and every single ladder rung stayed a tofu box.  The probes were valid — the slots that were
remapped carry real outlines (`U+058F` = 30-35 shape bytes against a 30-96 median), so this
is a genuine negative, not a blank-glyph false negative.

Guessing "which file" has run out of road.  So stop patching fonts and ask a different
question: **what can the ACTIVE font already draw?**  Character coverage is a fingerprint,
and the shipped fonts have sharply different ones:

    the 116-glyph Iggy set  : 95 ASCII + U+00A0 U+0107(ć) U+02C6(ˆ) U+02DC(˜)
                              U+2013(–) U+201C(") U+2022(•) U+20AC(€) U+2122(™)
                              -> NO Latin-1 accents, NO Cyrillic
    the SWF Cast / Arial    : + Latin-1 accents (é ü ñ) + 65 Cyrillic (ё) + CJK

So one line of ordinary text, with **no font file touched at all**, separates every case:

  * `4ć 5ˆ 6˜ 7– 8" 9• 10€ 11™` render but `1é 2ü 3ñ 12ё` box
        -> the active font IS a 116-glyph Iggy-style face.  fontlib.iggy is the right file
           and the code table is NOT the engine's lookup — the remaining work is finding the
           real glyph index inside the Iggy format.
  * `1é 2ü 3ñ` and/or `12ё` render
        -> the active font is an SWF face after all; the remap slot/approach was wrong.
  * EVERYTHING boxes except plain ASCII
        -> the game restricts the charset in its own code (TextDb / the Flash bridge), and
           **no amount of font work will ever help** — that would be the decisive stop sign.

This build changes ONLY text, so it is the cheapest and lowest-risk probe yet, and it runs
against PRISTINE font archives (`--revert` the font probes first) to keep one variable.

    python build_charset_probe.py --deploy | --revert | --verify
"""
import os
import sys
import shutil
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "tlou1", "tools"))
sys.path.insert(0, os.path.join(ROOT, "games", "uncharted_lot", "tools"))
sys.path.insert(0, HERE)

GAME = os.environ.get("UNC_GAME", r"F:\Game Lab\UNCHARTED - Legacy of Thieves Collection")
PC = os.path.join(GAME, "Uncharted4_data", "build", "pc")
TEXT_ARCS = [os.path.join(PC, g, "text2.psarc") for g in ("uncharted4", "thelostlegacy")]
os.environ.setdefault("TLOU_OODLE_DLL", os.path.join(GAME, "oo2core_9_win64.dll"))

from psarc import Psarc                     # noqa: E402
from psarc_write import repack              # noqa: E402
from oodle import Oodle                     # noqa: E402
import unc_loc                              # noqa: E402
import unc_backup                          # noqa: E402

MARKER = "ZZ-UNC-OK-ZZ"

# (rung, char, what it proves if it RENDERS)
CHARS = [
    (1,  "\u00e9", "e-acute   Latin-1  -> an SWF face (Cast/Arial), NOT the 116-glyph Iggy set"),
    (2,  "\u00fc", "u-umlaut  Latin-1  -> same"),
    (3,  "\u00f1", "n-tilde   Latin-1  -> same"),
    (4,  "\u0107", "c-acute   U+0107   -> the 116-glyph Iggy set (it is in that charset)"),
    (5,  "\u02c6", "circumflex U+02C6  -> Iggy set"),
    (6,  "\u02dc", "small tilde U+02DC -> Iggy set"),
    (7,  "\u2013", "en-dash   U+2013   -> Iggy set"),
    (8,  "\u201c", "left quote U+201C  -> Iggy set"),
    (9,  "\u2022", "bullet    U+2022   -> Iggy set"),
    (10, "\u20ac", "euro      U+20AC   -> Iggy set"),
    (11, "\u2122", "trademark U+2122   -> Iggy set"),
    (12, "\u0451", "yo        Cyrillic -> an SWF face with Cyrillic"),
    (13, "\u05d0", "alef      Hebrew   -> the target (expected to box)"),
]

PROBE_SHORT = " ".join(f"{r}{c}" for r, c, _ in CHARS[:7])
PROBE_FULL = (" ".join(f"{r}{c}" for r, c, _ in CHARS[:7]) + "  " +
              " ".join(f"{r}{c}" for r, c, _ in CHARS[7:]))

SURFACES = {
    "Press Any Button": MARKER, "START": MARKER,
    "Extras": PROBE_SHORT, "Options": PROBE_SHORT, "OPTIONS": PROBE_SHORT,
    "Chapter Select": PROBE_SHORT, "Credits": PROBE_SHORT, "Settings": PROBE_SHORT,
    "Load Game": PROBE_SHORT, "New Game": PROBE_SHORT, "Continue": PROBE_SHORT,
    "LOADING": PROBE_SHORT,
    "Quit to Desktop?": PROBE_FULL + "   " + MARKER,
    "Quit to Main Menu?": PROBE_FULL + "   " + MARKER,
}


def _entry(p, suffix):
    hits = [e for e in p.files() if e.path.endswith(suffix)]
    if not hits:
        raise KeyError(suffix)
    return hits[0]


def _backup(path):
    """Update-aware: keeps the pristine copy + records what we wrote."""
    return unc_backup.backup(path)


def build_text(src_psarc):
    p = Psarc(src_psarc)
    e = _entry(p, "eng.common")
    data = p.extract(e)
    cur = unc_loc.to_map(data)
    by = {}
    for sid, v in cur.items():
        by.setdefault(v, []).append(sid)
    ov = {sid: val for en, val in SURFACES.items() for sid in by.get(en, [])}
    new = unc_loc.encode(data, ov)
    back = unc_loc.to_map(new)
    for sid, want in ov.items():
        assert back[sid] == want
    assert not [s for s, v in cur.items() if s not in ov and back[s] != v]
    return {e.path: new}, len(ov)


def cmd_deploy(a):
    od = Oodle()
    print("== charset fingerprint (TEXT ONLY — no font file is touched) ==")
    for r, c, why in CHARS:
        print(f"  {r:>2} {c}  U+{ord(c):04X}  {why}")
    print(f"\n  short: {PROBE_SHORT}\n  full : {PROBE_FULL}\n")
    tmap, n = build_text(_backup(TEXT_ARCS[0]))
    for arc in TEXT_ARCS:
        _backup(arc)
        repack(arc + ".he_backup", tmap, arc, od)
        unc_backup.deploy_done(arc)
        print(f"  {os.path.relpath(arc, GAME)}  {os.path.getsize(arc):,} B")
    print(f"  {n} sid overrides")
    cmd_verify(a)


def cmd_revert(_a):
    n = 0
    for path in TEXT_ARCS:
        act, note = unc_backup.restore(path, force=getattr(_a, "force", False))
        rel = os.path.relpath(path, GAME)
        if act == "refused":
            print(f"  !! REFUSED {rel}")
            print(f"     {note}")
        elif act != "none":
            n += 1
            print(f"  {act:9s} {rel}" + (f"  ({note})" if note else ""))
    print(f"reverted {n} archive(s)" if n else "nothing to revert")


def cmd_verify(_a):
    print("== verify (reading the DEPLOYED archives) ==")
    for arc in TEXT_ARCS:
        q = Psarc(arc)
        vals = set(unc_loc.to_map(q.extract(_entry(q, "eng.common"))).values())
        print(f"  {os.path.relpath(arc, GAME)}: full={'YES' if any(PROBE_FULL in v for v in vals) else 'NO'}  "
              f"short={'YES' if PROBE_SHORT in vals else 'NO'}")


def main():
    ap = argparse.ArgumentParser(description="UNCHARTED LoT active-font charset fingerprint")
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="with --revert: DELETE a stale backup instead of "
                         "restoring it (use after a game update)")
    a = ap.parse_args()
    (cmd_revert if a.revert else cmd_verify if a.verify else
     cmd_deploy if a.deploy else lambda _: ap.print_help())(a)


if __name__ == "__main__":
    main()
