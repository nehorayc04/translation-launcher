#!/usr/bin/env python3
r"""
build_hebrew_proof.py — the REAL Hebrew menu proof: 27 injected glyphs in the LIVE font.

Everything upstream is now settled in-game:
  * container/text codec (reused from TLOU1, byte-identical round-trip),
  * mount + the sid overrides reach the menu,
  * bidi = NONE  ->  store VISUAL  (punctuation/digit placement in proof #5),
  * the live UI font = `fontlib-universal.swf` **id7 Albertus Medium** (proof #6: rung 6
    rendered the Euro; the vanish control on fontlib.swf id5 did NOT fire).

So this injects 27 real Hebrew outlines (David Libre Bold) into id7 via the proven
extend-and-serialize path (`unc_font_swf`, 16/16 offline), then deploys the standing proof
recipe, stored VISUAL:
  * a pure-Latin MARKER (mount, font-independent),
  * the full 27-letter alphabet (glyph COVERAGE — any missing letter shows as a box),
  * real Hebrew menu labels (does it read like a menu),
  * a Hebrew TEST PARAGRAPH with punctuation / digits / parens / quotes / a Latin island
    (neutral placement under the real UBA),
  * a bidi A/B: the SAME word stored VISUAL vs LOGICAL + a 4-letter control, so the user
    TRANSCRIBES which reads right ([[hebrew-screenshot-transcription-trap]]).

Every modified SWF body is gated through `unc_swf.validate()` before repack (the
black-screen guard, [[aliased-offset-black-screens]]).

    python build_hebrew_proof.py --deploy | --revert | --verify
"""
import os
import sys
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "tlou1", "tools"))
sys.path.insert(0, os.path.join(ROOT, "games", "uncharted_lot", "tools"))
sys.path.insert(0, os.path.join(ROOT, "games", "witcher3", "work"))
sys.path.insert(0, HERE)

GAME = os.environ.get("UNC_GAME", r"F:\Game Lab\UNCHARTED - Legacy of Thieves Collection")
PC = os.path.join(GAME, "Uncharted4_data", "build", "pc")
TEXT_ARCS = [os.path.join(PC, g, "text2.psarc") for g in ("uncharted4", "thelostlegacy")]
FLASH_ARC = os.path.join(PC, "main", "flash1.psarc")
os.environ.setdefault("TLOU_OODLE_DLL", os.path.join(GAME, "oo2core_9_win64.dll"))

from psarc import Psarc                     # noqa: E402
from psarc_write import repack              # noqa: E402
from oodle import Oodle                     # noqa: E402
from bidi.algorithm import get_display      # noqa: E402
import unc_loc                              # noqa: E402
import unc_backup                           # noqa: E402
import unc_swf                              # noqa: E402
import unc_font_swf as FX                   # noqa: E402

TARGET_SWF = "fontlib-universal.swf"
TARGET_ID = 7                               # Albertus Medium — proven live in proof #6
MARKER = "ZZ-UNC-OK-ZZ"

# the 27 letters in alphabetical order (base 22 + 5 finals), for a glyph-coverage row
ALPHABET = "אבגדהוזחטיכךלמםנןסעפףץצקרשת"
PARA = ('בדיקת עברית: שלום, זהו משפט לדוגמה (עם סוגריים) ומספרים 12345. '
        'האם הטקסט קריא? "מרכאות" — מקף. Uncharted 4.')


def V(s):
    """store VISUAL: run the real UBA with an RTL base (engine does no bidi of its own)."""
    return get_display(s, base_dir="R")


# English menu key -> what to store (already VISUAL where Hebrew)
SURFACES = {
    "Press Any Button": MARKER, "START": MARKER, "LOADING": MARKER,
    "Continue": V("המשך"),
    "New Game": V("משחק חדש"),
    "Load Game": V("טען משחק"),
    "Options": V("אפשרויות"), "OPTIONS": V("אפשרויות"), "Settings": V("אפשרויות"),
    "Extras": V("תוספות"),
    "Chapter Select": V("בחירת פרק"),
    "Credits": V(ALPHABET),                       # 27-letter coverage row
    # the Quit dialog carries marker + paragraph + the bidi A/B control
    "Quit to Desktop?":   MARKER + "  " + V(PARA) + "   " + V("שלום") + " | " + "שלום" + " | " + V("אבגד"),
    "Quit to Main Menu?": MARKER + "  " + V(PARA) + "   " + V("שלום") + " | " + "שלום" + " | " + V("אבגד"),
}


def _entry(p, suffix):
    hits = [e for e in p.files() if e.path.endswith(suffix)]
    if not hits:
        raise KeyError(suffix)
    return hits[0]


def _backup(path):
    return unc_backup.backup(path)


def build_flash(src_psarc):
    p = Psarc(src_psarc)
    e = _entry(p, TARGET_SWF)
    body, form = unc_swf.decompress(p.extract(e))
    body, added, scale = FX.extend_font(body, TARGET_ID)
    probs = unc_swf.validate(body, where=f"{TARGET_SWF} ")
    if probs:
        raise RuntimeError("STRUCTURAL DEFECT — refusing to deploy:\n  " + "\n  ".join(probs))
    return {e.path: unc_swf.recompress(body, form)}, added, scale


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
    print(f"== inject 27 Hebrew into {TARGET_SWF} id{TARGET_ID} (Albertus Medium) ==")
    fmap, added, scale = build_flash(_backup(FLASH_ARC))
    print(f"  scale={scale:.3f}  added {len(added)} glyphs, structurally validated")
    tmap, n = build_text(_backup(TEXT_ARCS[0]))
    print(f"  text: {n} sid overrides (stored VISUAL)")
    print("== repack + deploy ==")
    repack(FLASH_ARC + ".he_backup", fmap, FLASH_ARC, od)
    unc_backup.deploy_done(FLASH_ARC)
    print(f"  {os.path.basename(FLASH_ARC)}  {os.path.getsize(FLASH_ARC):,} B")
    for arc in TEXT_ARCS:
        _backup(arc)
        repack(arc + ".he_backup", tmap, arc, od)
        unc_backup.deploy_done(arc)
        print(f"  {os.path.relpath(arc, GAME)}  {os.path.getsize(arc):,} B")
    cmd_verify(a)


def cmd_revert(_a):
    n = 0
    for path in [FLASH_ARC] + TEXT_ARCS:
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
    ok = True
    p = Psarc(FLASH_ARC)
    body, _ = unc_swf.decompress(p.extract(_entry(p, TARGET_SWF)))
    f = [x for x in unc_swf.fonts(body) if x["id"] == TARGET_ID][0]
    heb = [c for c in f["codes"] if 0x05D0 <= c <= 0x05EA]
    clean = not unc_swf.validate(body)
    ok &= len(heb) == 27 and f["codes"] == sorted(f["codes"]) and clean
    print(f"  {TARGET_SWF} id{TARGET_ID}: {f['n']} glyphs, Hebrew {len(heb)}/27, "
          f"sorted={f['codes']==sorted(f['codes'])}, struct={'ok' if clean else 'BAD'}")
    for arc in TEXT_ARCS:
        q = Psarc(arc)
        vals = set(unc_loc.to_map(q.extract(_entry(q, "eng.common"))).values())
        hasmark = any(MARKER in v for v in vals)
        hasalef = any(V(ALPHABET) == v for v in vals)
        ok &= hasmark and hasalef
        print(f"  {os.path.relpath(arc, GAME)}: marker={'YES' if hasmark else 'NO'} "
              f"alphabet={'YES' if hasalef else 'NO'}")
    print("  ALL CHECKS PASS" if ok else "  !! something did not apply")


def main():
    ap = argparse.ArgumentParser(description="UNCHARTED LoT — real Hebrew menu proof")
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="with --revert: delete a stale backup after a game update")
    a = ap.parse_args()
    (cmd_revert if a.revert else cmd_verify if a.verify else
     cmd_deploy if a.deploy else lambda _: ap.print_help())(a)


if __name__ == "__main__":
    main()
