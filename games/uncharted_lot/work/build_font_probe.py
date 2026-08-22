#!/usr/bin/env python3
r"""
build_font_probe.py — PROOF #2 for UNCHARTED: Legacy of Thieves.

Proof #1 answered two gates and raised one:
  ✅ MOUNT   — the loc repack loads (glyph COUNT on screen matched the Hebrew exactly:
               4 boxes for `אבגד`, 8 for `אפשרויות`, 2+2 for the `כן`/`לא` buttons).
  ✅ BIDI    — NONE.  Read straight off the tofu, without a single glyph: the stored
               LOGICAL `בדיקת עברית: שלום, זהו משפט` rendered as
               `□□□□□ □□□□□ : □□□□ , □□□ □□□□`, i.e. the colon after 5+5 and the comma
               after 4 — exact STORAGE order, with `12345.` opening a line and
               `Uncharted 4.` closing it.  RTL reordering would have inverted that.
               ⇒ store **VISUAL**, same class as TLOU1/TLOU2/AC2/Anno.
  ❓ FONT    — the Hebrew was tofu while the Latin was perfect, so the surface is NOT the
               `main.fnt` bitmap atlas that proof #1 injected.  It is Iggy.

This proof names the Iggy font behind each surface, and it costs NOTHING structurally: an
Iggy code table is a plain ascending u16 array, so remapping one codepoint is a **delta-0
two-byte edit** — no glyph data, no offsets, no pointer fix-ups, no size change.

METHOD — a LADDER, and the answer is a NUMBER the user reads.
`fontlib.iggy` holds all 6 fonts; every other UI library references them by name, so one
file covers the whole game.  Each font gets TWO remapped slots, and every probe letter is
printed next to its own index, e.g. `1א 2ב 3ג 4ד 5ה 6ו   7ז 8ח 9ט 10י 11כ 12ל`.

  * indices 1-6  -> table index 99 (`U+2013`) per font, ORDER-SAFE
                    (neighbours U+02DC and U+2014, so U+05D0..U+05D5 keeps it ascending).
                    The number beside the non-box NAMES the font that surface uses.
  * indices 7-12 -> table index 115 (`U+2122`, the LAST element) per font, deliberately
                    ORDER-BREAKING.  Violating only the final entry cannot disturb a binary
                    search over the low/ASCII range, so Latin stays safe.  If these render
                    too, the table need NOT stay ascending — which decides the injection
                    budget: ascending-only leaves 21 usable slots (indices 95..115) for 27
                    Hebrew letters, order-free means any slot will do.

⚠️ Round 1 used a bare `אבגדהו` and the probe WORKED (the user reported "a mark and boxes"),
but the result was unreadable — an en-dash among tofu boxes cannot be placed by eye.  Never
make the user count positions: attach a digit to each candidate, since digits render from
the untouched ASCII glyphs and are always legible.

    python build_font_probe.py --deploy | --revert | --verify
"""
import os
import sys
import struct
import shutil
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "tlou1", "tools"))
sys.path.insert(0, os.path.join(ROOT, "games", "uncharted_lot", "tools"))
sys.path.insert(0, HERE)

GAME = os.environ.get("UNC_GAME", r"F:\Game Lab\UNCHARTED - Legacy of Thieves Collection")
TEXT_ARCS = [os.path.join(GAME, "Uncharted4_data", "build", "pc", g, "text2.psarc")
             for g in ("uncharted4", "thelostlegacy")]
IGGY_ARC = os.path.join(GAME, "Uncharted4_data", "build", "pc", "main", "iggy1.psarc")
os.environ.setdefault("TLOU_OODLE_DLL", os.path.join(GAME, "oo2core_9_win64.dll"))

from psarc import Psarc                     # noqa: E402
from psarc_write import repack              # noqa: E402
from oodle import Oodle                     # noqa: E402
import unc_loc                              # noqa: E402
import unc_backup                          # noqa: E402
import unc_iggy                             # noqa: E402

MARKER = "ZZ-UNC-OK-ZZ"

# --- round 2 -----------------------------------------------------------------
# Round 1 worked (the user saw "a mark and boxes") — so the Iggy code table IS the
# engine's lookup and a delta-0 remap really lands.  But a bare `אבגדהו` made the
# ANSWER unreadable: an en-dash among boxes is impossible to place by eye.  So every
# probe letter now carries its own NUMBER, and the user just reads the number next to
# the non-box.  Digits render natively, so they are always legible.
#
# Two questions per launch:
#   letters 1-6  = index 99  (U+2013 -> U+05D0+k)   ORDER-SAFE  -> names the font
#   letters 7-12 = index 115 (U+2122 -> U+05D6+k)   ORDER-BREAKING (last element, so a
#                  binary search over the low/ASCII range is unaffected) -> tells us
#                  whether the table must stay ascending.
# That second bit decides the whole injection budget: ascending-only leaves 21 usable
# slots (indices 95..115) for 27 Hebrew letters, while order-free means ANY slot works.
SAFE_INDEX = 99           # U+2013 in all 6 tables
BREAK_INDEX = 115         # U+2122 in all 6 tables — violating only the LAST element
SAFE_CPS = [0x05D0, 0x05D1, 0x05D2, 0x05D3, 0x05D4, 0x05D5]          # א ב ג ד ה ו
# deliberately NO final forms (ך ם ן ף ץ) — at menu size they are easy to misread
BREAK_CPS = [0x05D6, 0x05D7, 0x05D8, 0x05D9, 0x05DB, 0x05DC]         # ז ח ט י כ ל

PROBE_SHORT = "".join(f"{k+1}{chr(SAFE_CPS[k])}" for k in range(6))
PROBE_FULL = (" ".join(f"{k+1}{chr(SAFE_CPS[k])}" for k in range(6)) + "   " +
              " ".join(f"{k+7}{chr(BREAK_CPS[k])}" for k in range(6)))

# every surface reachable without playing; each reports its own font independently.
# Roomy surfaces get the FULL 12-letter probe (font id + ordering test); tight menu rows
# get the compact 6-letter one so they do not clip.
SURFACES = {
    "Press Any Button":   MARKER,
    "START":              MARKER,
    "Extras":             PROBE_SHORT,
    "Options":            PROBE_SHORT,
    "OPTIONS":            PROBE_SHORT,
    "Chapter Select":     PROBE_SHORT,
    "Credits":            PROBE_SHORT,
    "Settings":           PROBE_SHORT,
    "Load Game":          PROBE_SHORT,
    "New Game":           PROBE_SHORT,
    "Continue":           PROBE_SHORT,
    "Back":               PROBE_SHORT,
    "Cancel":             PROBE_SHORT,
    "Yes":                PROBE_SHORT,
    "No":                 PROBE_SHORT,
    "LOADING":            PROBE_SHORT,
    "L O A D I N G":      PROBE_SHORT,
    "Quit to Desktop?":   PROBE_FULL + "   " + MARKER,
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


def build_iggy(src_psarc):
    p = Psarc(src_psarc)
    e = _entry(p, "fontlib.iggy")
    b = p.extract(e)
    tabs = unc_iggy.find_code_tables(b)
    if len(tabs) != 6:
        raise AssertionError(f"expected 6 code tables, found {len(tabs)}")
    # the 6th table's name is not stored after it (the only face left over is this one);
    # `face_name` finds the AS3 scene name there instead, so pin it explicitly.
    LEFTOVER = "Alte Haas Grotesk Bold"
    rows = []
    for k, off in enumerate(tabs):
        n = len(unc_iggy.read_table(b, off))
        face = unc_iggy.face_name(b, off + 2 * n)
        if " " not in face or face.startswith("Scene"):
            face = LEFTOVER
        b, old_safe = unc_iggy.remap(b, off, SAFE_INDEX, SAFE_CPS[k])
        # the ordering test deliberately violates ascending order, so bypass the guard
        b, old_break = unc_iggy.remap_unchecked(b, off, BREAK_INDEX, BREAK_CPS[k])
        rows.append((k, off, face, old_safe, SAFE_CPS[k], old_break, BREAK_CPS[k]))
    assert len(b) == len(p.extract(e)), "iggy patch must be delta-0"
    return {e.path: b}, rows


def build_text(src_psarc):
    p = Psarc(src_psarc)
    e = _entry(p, "eng.common")
    data = p.extract(e)
    cur = unc_loc.to_map(data)
    by_text = {}
    for sid, v in cur.items():
        by_text.setdefault(v, []).append(sid)
    ov, miss = {}, []
    for en, val in SURFACES.items():
        sids = by_text.get(en, [])
        if not sids:
            miss.append(en)
        for sid in sids:
            ov[sid] = val
    new = unc_loc.encode(data, ov)
    back = unc_loc.to_map(new)
    for sid, want in ov.items():
        assert back[sid] == want, sid
    assert not [s for s, v in cur.items() if s not in ov and back[s] != v], "collateral change"
    return {e.path: new}, len(ov), miss


def cmd_deploy(a):
    od = Oodle()
    print("== iggy font code-table probe (delta-0) ==")
    imap, rows = build_iggy(_backup(IGGY_ARC))
    for k, off, face, os_, cs, ob, cb in rows:
        print(f"  font {k} {face:26s} safe[{SAFE_INDEX}] U+{os_:04X}->U+{cs:04X} {chr(cs)} (num {k+1})"
              f"   break[{BREAK_INDEX}] U+{ob:04X}->U+{cb:04X} {chr(cb)} (num {k+7})")
    print(f"  short probe: {PROBE_SHORT}")
    print(f"  full  probe: {PROBE_FULL}")
    print("== text ==")
    tmap, n, miss = build_text(_backup(TEXT_ARCS[0]))
    print(f"  {n} sid overrides across {len(SURFACES)} surfaces" + (f"  MISSING={miss}" if miss else ""))
    print("== repack + deploy ==")
    repack(IGGY_ARC + ".he_backup", imap, IGGY_ARC, od)
    print(f"  iggy1.psarc  {os.path.getsize(IGGY_ARC):,} B")
    for arc in TEXT_ARCS:
        _backup(arc)
        repack(arc + ".he_backup", tmap, arc, od)
        unc_backup.deploy_done(arc)
        print(f"  {os.path.relpath(arc, GAME)}  {os.path.getsize(arc):,} B")
    cmd_verify(a)


def cmd_revert(_a):
    n = 0
    for path in [IGGY_ARC] + TEXT_ARCS:
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
    p = Psarc(IGGY_ARC)
    b = p.extract(_entry(p, "fontlib.iggy"))
    for k, off in enumerate(unc_iggy.find_code_tables(b)):
        t = [struct.unpack_from("<H", b, off + 2 * i)[0] for i in range(117)]
        ok_s = t[SAFE_INDEX] == SAFE_CPS[k]
        ok_b = t[BREAK_INDEX] == BREAK_CPS[k]
        print(f"  font {k}: [{SAFE_INDEX}]=U+{t[SAFE_INDEX]:04X} {'OK' if ok_s else 'BAD'}   "
              f"[{BREAK_INDEX}]=U+{t[BREAK_INDEX]:04X} {'OK' if ok_b else 'BAD'}")
    for arc in TEXT_ARCS:
        q = Psarc(arc)
        vals = set(unc_loc.to_map(q.extract(_entry(q, "eng.common"))).values())
        print(f"  {os.path.relpath(arc, GAME)}: short={'YES' if PROBE_SHORT in vals else 'NO'}  "
              f"full={'YES' if any(PROBE_FULL in v for v in vals) else 'NO'}  "
              f"marker={'YES' if any(MARKER in v for v in vals) else 'NO'}")


def main():
    ap = argparse.ArgumentParser(description="UNCHARTED LoT Iggy font-identification probe")
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="with --revert: DELETE a stale backup instead of "
                         "restoring it (use after a game update)")
    a = ap.parse_args()
    if a.revert:
        cmd_revert(a)
    elif a.verify:
        cmd_verify(a)
    elif a.deploy:
        cmd_deploy(a)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
