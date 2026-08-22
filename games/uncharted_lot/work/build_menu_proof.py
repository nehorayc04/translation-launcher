#!/usr/bin/env python3
r"""
build_menu_proof.py — the ONE-LAUNCH Hebrew proof for UNCHARTED: Legacy of Thieves.

Bundles every open Phase-1 question into a single deployed build so one launch closes
them all:

  1. MOUNT      — a pure-Latin marker `ZZ-UNC-OK-ZZ` on the first screen.  It renders
                  with the game's OWN Latin glyphs, so it separates "the repack did not
                  load" from "the font has no Hebrew" — which otherwise look identical.
  2. SURFACE    — the game has TWO text renderers (Iggy/Flash for menus, the native
                  BMFont atlas for HUD/loading).  Hebrew is injected ONLY into the native
                  atlas (`main.fnt`), so whichever surface shows Hebrew identifies itself.
  3. BIDI       — the SAME word is stored LOGICAL on one row and VISUAL on another.
                  Exactly one of them can read `שלום`; that names the engine's mode.
                  A 4-distinct-letter control `אבגד` guards against final-form ambiguity.
  4. GLYPHS     — all 27 Hebrew letters on one row, so a missing/broken glyph is visible.
  5. LAYOUT     — a real Hebrew paragraph with punctuation, parentheses, quotes, digits
                  and a Latin island, in BOTH modes, to expose wrap and spacing.

Everything is keyed by ENGLISH TEXT and applied to EVERY sid carrying it, because several
menu items exist under 2-3 sids and which one the live menu uses is unknown — patching all
of them removes the guess.

    python build_menu_proof.py --deploy      # backup + patch + repack + install
    python build_menu_proof.py --revert      # restore the .he_backup files
    python build_menu_proof.py --verify      # read the DEPLOYED archives back
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
TEXT_ARCS = [os.path.join(GAME, "Uncharted4_data", "build", "pc", g, "text2.psarc")
             for g in ("uncharted4", "thelostlegacy")]
FONT_ARC = os.path.join(GAME, "Uncharted4_data", "data", "fonts.psarc")
OODLE = os.path.join(GAME, "oo2core_9_win64.dll")
os.environ.setdefault("TLOU_OODLE_DLL", OODLE)

from psarc import Psarc                     # noqa: E402
from psarc_write import repack              # noqa: E402
from oodle import Oodle                     # noqa: E402
import unc_loc                              # noqa: E402
import unc_backup                          # noqa: E402
import unc_font                             # noqa: E402
from bidi.algorithm import get_display      # noqa: E402

MARKER = "ZZ-UNC-OK-ZZ"
ALEPHBET = "אבגדהוזחטיכךלמםנןסעפףצץקרשת"      # all 27, ordered a-t with the finals inline
PARA = ('בדיקת עברית: שלום, זהו משפט לדוגמה (עם סוגריים) ומספרים 12345. '
        'האם הטקסט קריא? "מרכאות" — מקף. Uncharted 4.')


def visual(s):
    """Store-VISUAL form: run the real UBA with an RTL base (never hand-rolled)."""
    return get_display(s, base_dir="R")


# english text -> (value, mode)   mode: "raw" | "logical" | "visual"
PROOF = {
    # --- 1. mount: pure Latin, needs no Hebrew glyph at all -------------------
    "Press Any Button":  (MARKER,                    "raw"),
    "START":             (MARKER,                    "raw"),
    # --- 3. bidi A/B: exactly one of these can read "שלום" --------------------
    "Continue":          ("שלום",                    "logical"),
    "New Game":          ("שלום",                    "visual"),
    "Extras":            ("אבגד",                    "logical"),   # 4-distinct control
    "Chapter Select":    ("אבגד",                    "visual"),
    # --- 4. glyph coverage ----------------------------------------------------
    "Credits":           (ALEPHBET,                  "logical"),
    # --- ordinary words, both modes ------------------------------------------
    "Options":           ("אפשרויות",                "logical"),
    "OPTIONS":           ("אפשרויות",                "visual"),
    "Settings":          ("הגדרות ABC",              "logical"),
    "Load Game":         ("טען משחק 123",            "logical"),
    "Yes":               ("כן",                      "logical"),
    "No":                ("לא",                      "logical"),
    "Back":              ("חזור",                    "logical"),
    "Cancel":            ("ביטול",                   "logical"),
    # --- 2. native-renderer surface (loading screen, not the Flash menu) ------
    "LOADING":           ("טוען משחק",               "logical"),
    "L O A D I N G":     ("ט ו ע ן",                 "logical"),
    # --- 5. paragraph, same text in BOTH modes -------------------------------
    "Quit to Desktop?":   (PARA,                     "logical"),
    "Quit to Main Menu?": (PARA,                     "visual"),
}


def _render(val, mode):
    return val if mode in ("raw", "logical") else visual(val)


def _entry(p, suffix):
    hits = [e for e in p.files() if e.path.endswith(suffix)]
    if not hits:
        raise KeyError(suffix)
    return hits[0]


def build_text(src_psarc):
    """-> {archive_path: new_bytes} for the loc archive."""
    p = Psarc(src_psarc)
    e = _entry(p, "eng.common")
    data = p.extract(e)
    cur = unc_loc.to_map(data)
    by_text = {}
    for sid, v in cur.items():
        by_text.setdefault(v, []).append(sid)

    overrides, report = {}, []
    for en, (val, mode) in PROOF.items():
        sids = by_text.get(en, [])
        if not sids:
            report.append((en, mode, 0, "NOT FOUND"))
            continue
        out = _render(val, mode)
        for sid in sids:
            overrides[sid] = out
        report.append((en, mode, len(sids), out[:46]))
    new = unc_loc.encode(data, overrides)

    # read-back check before it ever reaches the game
    back = unc_loc.to_map(new)
    for sid, want in overrides.items():
        if back[sid] != want:
            raise AssertionError(f"override round-trip failed for {sid}")
    untouched = sum(1 for sid, v in cur.items() if sid not in overrides and back[sid] != v)
    if untouched:
        raise AssertionError(f"{untouched} untouched strings changed!")
    return {e.path: new}, report, len(overrides)


def build_font(src_psarc):
    """-> {archive_path: new_bytes} for the font archive."""
    p = Psarc(src_psarc)
    fe, te = _entry(p, "main.fnt"), _entry(p, "main_00.tga")
    fnt = p.extract(fe).decode("utf-8", "replace")
    tmp_tga = os.path.join(HERE, "out", "_src_main_00.tga")
    os.makedirs(os.path.dirname(tmp_tga), exist_ok=True)
    open(tmp_tga, "wb").write(p.extract(te))

    new_fnt, arr, t, meta = unc_font.inject(fnt, tmp_tga)
    out_tga = os.path.join(HERE, "out", "main_00.tga")
    out_fnt = os.path.join(HERE, "out", "main.fnt")
    unc_font.write_tga(t, arr, out_tga)
    open(out_fnt, "w", encoding="utf-8", newline="").write(new_fnt)
    return {fe.path: open(out_fnt, "rb").read(), te.path: open(out_tga, "rb").read()}, meta


def _backup(path):
    """Update-aware: keeps the pristine copy + records what we wrote."""
    return unc_backup.backup(path)


def cmd_deploy(_a):
    od = Oodle()
    print("== font ==")
    fmap, meta = build_font(_backup(FONT_ARC))
    print(f"  {meta['count']} Hebrew glyphs, donor {meta['size']}px, body {meta['body']}px "
          f"vs latin cap {meta['cap']}px")

    print("== text ==")
    tmap, report, n = build_text(_backup(TEXT_ARCS[0]))
    for en, mode, k, out in report:
        flag = "  " if k else "!!"
        print(f"  {flag} {en:22s} [{mode:7s}] x{k}  {out}")
    print(f"  -> {n} sid overrides")

    print("== repack + deploy ==")
    repack(FONT_ARC + ".he_backup", fmap, FONT_ARC, od)
    print(f"  fonts.psarc  {os.path.getsize(FONT_ARC):,} B")
    for arc in TEXT_ARCS:
        _backup(arc)
        repack(arc + ".he_backup", tmap, arc, od)
        unc_backup.deploy_done(arc)
        print(f"  {os.path.relpath(arc, GAME)}  {os.path.getsize(arc):,} B")
    cmd_verify(_a)


def cmd_revert(_a):
    n = 0
    for path in [FONT_ARC] + TEXT_ARCS:
        b = path + ".he_backup"
        if os.path.exists(b):
            shutil.copy2(b, path)
            os.remove(b)
            n += 1
            print(f"  restored {os.path.relpath(path, GAME)}")
    print(f"reverted {n} archive(s)" if n else "nothing to revert")


def cmd_verify(_a):
    """Read the DEPLOYED archives back off disk — never trust the builder."""
    print("== verify (reading the deployed archives) ==")
    p = Psarc(FONT_ARC)
    fnt = p.extract(_entry(p, "main.fnt")).decode("utf-8", "replace")
    info, common, chars = unc_font.parse_fnt(fnt)
    have = {c["id"] for c in chars}
    miss = [cp for cp in unc_font.HEBREW if cp not in have]
    print(f"  fonts.psarc: atlas {common['scaleW']}x{common['scaleH']}  chars={len(chars)}  "
          f"hebrew={27-len(miss)}/27" + (f"  MISSING={miss}" if miss else ""))
    for arc in TEXT_ARCS:
        q = Psarc(arc)
        m = unc_loc.to_map(q.extract(_entry(q, "eng.common")))
        vals = set(m.values())
        heb = sum(1 for v in vals if any("\u05d0" <= ch <= "\u05ea" for ch in v))
        print(f"  {os.path.relpath(arc, GAME)}: {len(m):,} sids, marker={'YES' if MARKER in vals else 'NO'}, "
              f"hebrew strings={heb}")


def main():
    ap = argparse.ArgumentParser(description="UNCHARTED LoT one-launch Hebrew proof")
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="with --revert: DELETE a stale backup instead of "
                         "restoring it (use after a game update)")
    a = ap.parse_args()
    if not os.path.isdir(GAME):
        sys.exit(f"game not found: {GAME}")
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
