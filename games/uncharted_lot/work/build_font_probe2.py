#!/usr/bin/env python3
r"""
build_font_probe2.py — PROOF #4: sweep EVERY candidate font source in one launch.

Where we are:
  ✅ mount + bidi(=none, store VISUAL) settled by proof #1.
  ✗  `main.fnt` bitmap atlas — patched, no effect.
  ✗  `fontlib.iggy` code tables — 12 remaps across all 6 fonts, **no effect**
     (proof #3: every ladder position stayed tofu, order-safe AND order-breaking).

So the UI glyphs come from somewhere neither of those covers.  This build probes the
remaining candidates simultaneously, each on its own numbered rung:

  1-5   `flash1.psarc/fontlib.swf`            Cast-Bold, Comic Sans, Arial Unicode MS,
                                              Cast-Regular, Albertus Medium
  6-9   `flash1.psarc/fontlib-universal.swf`  Cast Bold, Arial Unicode MS, Cast Regular,
                                              Albertus Medium
  10    `iggy1.psarc/controller-movie.iggy`   Albertus Medium (full 115-glyph ASCII set)
  11-12 `iggy1.psarc/fontlib.iggy`            Albertus Medium + Alte Haas Grotesk Bold
                                              (deliberate control — expected to stay tofu)

Why the SWF side is now the prime suspect:
  * `flash1.psarc` ships **five** fontlib variants (`fontlib`, `-universal`, `-sceasia`,
    `-scechina`, `-scej`) while `iggy1.psarc` has only ONE `fontlib.iggy`.  A game shipping
    JP/KO/ZH must load the regional libraries, and those exist ONLY as `.swf`.
  * the exe's `IggyFileImage` loader holds both pak names, the `swf` extension, a literal
    `%s.swf`, and a `hashMatches` check.
  * `flash1.psarc`'s last-access time moved during a real play session.
  * the per-library subset fonts in `fmenu.iggy`/`ndmenus.iggy` are ruled OUT by their own
    charset: neither contains **Q**, yet the menu renders "Quit to Desktop".

🔑 Every SWF font turned out to carry a **U+058F** entry (the Armenian dram sign) sitting
between Cyrillic U+0451 and Arabic U+060B — an unused symbol in exactly the right place, so
Hebrew drops in **order-safe and delta-0** in all of them.

    python build_font_probe2.py --deploy | --revert | --verify
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
FLASH_ARC = os.path.join(PC, "main", "flash1.psarc")
IGGY_ARC = os.path.join(PC, "main", "iggy1.psarc")
os.environ.setdefault("TLOU_OODLE_DLL", os.path.join(GAME, "oo2core_9_win64.dll"))

from psarc import Psarc                     # noqa: E402
from psarc_write import repack              # noqa: E402
from oodle import Oodle                     # noqa: E402
import unc_loc                              # noqa: E402
import unc_backup                          # noqa: E402
import unc_iggy                             # noqa: E402
import unc_swf                              # noqa: E402

MARKER = "ZZ-UNC-OK-ZZ"
# no final forms — they are easy to misread at menu size
LETTERS = [0x05D0, 0x05D1, 0x05D2, 0x05D3, 0x05D4, 0x05D5,
           0x05D6, 0x05D7, 0x05D8, 0x05D9, 0x05DB, 0x05DC]   # א ב ג ד ה ו ז ח ט י כ ל

# (rung, archive-kind, entry suffix, font selector)  -- selector: SWF font id, or iggy table index
PLAN = [
    (1,  "swf",  "fontlib.swf",           1),    # Cast-Bold
    (2,  "swf",  "fontlib.swf",           2),    # Comic Sans MS
    (3,  "swf",  "fontlib.swf",           3),    # Arial Unicode MS Regular
    (4,  "swf",  "fontlib.swf",           4),    # Cast-Regular
    (5,  "swf",  "fontlib.swf",           5),    # Albertus Medium
    (6,  "swf",  "fontlib-universal.swf", 1),    # Cast Bold
    (7,  "swf",  "fontlib-universal.swf", 4),    # Arial Unicode MS Regular
    (8,  "swf",  "fontlib-universal.swf", 6),    # Cast Regular
    (9,  "swf",  "fontlib-universal.swf", 7),    # Albertus Medium
    (10, "iggy", "controller-movie.iggy", 0),    # Albertus Medium, full ASCII
    (11, "iggy", "fontlib.iggy",          3),    # Albertus Medium   (control)
    (12, "iggy", "fontlib.iggy",          5),    # Alte Haas Grotesk Bold (control)
]

PROBE_SHORT = "".join(f"{r}{chr(LETTERS[r-1])}" for r in range(1, 7))
PROBE_FULL = (" ".join(f"{r}{chr(LETTERS[r-1])}" for r in range(1, 7)) + "  " +
              " ".join(f"{r}{chr(LETTERS[r-1])}" for r in range(7, 13)))

SURFACES = {
    "Press Any Button": MARKER, "START": MARKER,
    "Extras": PROBE_SHORT, "Options": PROBE_SHORT, "OPTIONS": PROBE_SHORT,
    "Chapter Select": PROBE_SHORT, "Credits": PROBE_SHORT, "Settings": PROBE_SHORT,
    "Load Game": PROBE_SHORT, "New Game": PROBE_SHORT, "Continue": PROBE_SHORT,
    "Back": PROBE_SHORT, "Cancel": PROBE_SHORT, "Yes": PROBE_SHORT, "No": PROBE_SHORT,
    "LOADING": PROBE_SHORT, "L O A D I N G": PROBE_SHORT,
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


def build_archive(src_psarc, kind):
    """Patch every PLAN row whose archive kind matches. -> ({path: bytes}, rows)."""
    p = Psarc(src_psarc)
    files, rows = {}, []
    for rung, k, name, sel in PLAN:
        if k != kind:
            continue
        e = _entry(p, name)
        b = files.get(e.path) or p.extract(e)
        cp = LETTERS[rung - 1]
        if kind == "swf":
            body, form = unc_swf.decompress(b)
            fs = [f for f in unc_swf.fonts(body) if f["id"] == sel]
            if not fs:
                raise KeyError(f"{name}: no DefineFont3 id={sel}")
            f = fs[0]
            idx = unc_swf.plan_slot(f["codes"], cp)
            if idx is None:
                raise ValueError(f"{name} id={sel}: no order-safe slot for U+{cp:04X}")
            body, old = unc_swf.patch(body, f, idx, cp)
            files[e.path] = unc_swf.recompress(body, form)
            rows.append((rung, name, f["name"], f"slot {idx}", old, cp))
        else:
            tabs = unc_iggy.find_code_tables(b, min_len=60)
            off = tabs[sel]
            t = unc_iggy.read_table(b, off)
            idx = unc_swf.plan_slot(t, cp)
            if idx is None:
                raise ValueError(f"{name}[{sel}]: no order-safe slot for U+{cp:04X}")
            face = unc_iggy.face_name(b, off + 2 * len(t))
            b, old = unc_iggy.remap(b, off, idx, cp)
            files[e.path] = b
            rows.append((rung, name, face, f"idx {idx}", old, cp))
    return files, rows


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
    out = []
    for arc, kind in ((FLASH_ARC, "swf"), (IGGY_ARC, "iggy")):
        fmap, rows = build_archive(_backup(arc), kind)
        for rung, name, face, where, old, cp in rows:
            print(f"  rung {rung:>2}  {name:24s} {face:26s} {where:9s} "
                  f"U+{old:04X} -> U+{cp:04X} {chr(cp)}")
        out.append((arc, fmap))
    tmap, n = build_text(_backup(TEXT_ARCS[0]))
    print(f"  text: {n} sid overrides")
    print(f"  short: {PROBE_SHORT}\n  full : {PROBE_FULL}")
    print("== repack + deploy ==")
    for arc, fmap in out:
        repack(arc + ".he_backup", fmap, arc, od)
        print(f"  {os.path.basename(arc)}  {os.path.getsize(arc):,} B  ({len(fmap)} entries)")
    for arc in TEXT_ARCS:
        _backup(arc)
        repack(arc + ".he_backup", tmap, arc, od)
        unc_backup.deploy_done(arc)
        print(f"  {os.path.relpath(arc, GAME)}  {os.path.getsize(arc):,} B")
    cmd_verify(a)


def cmd_revert(_a):
    n = 0
    for path in [FLASH_ARC, IGGY_ARC] + TEXT_ARCS:
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
    for arc, kind in ((FLASH_ARC, "swf"), (IGGY_ARC, "iggy")):
        p = Psarc(arc)
        for rung, k, name, sel in PLAN:
            if k != kind:
                continue
            b = p.extract(_entry(p, name))
            cp = LETTERS[rung - 1]
            if kind == "swf":
                body, _ = unc_swf.decompress(b)
                f = [x for x in unc_swf.fonts(body) if x["id"] == sel][0]
                ok = cp in f["codes"]
            else:
                t = unc_iggy.read_table(b, unc_iggy.find_code_tables(b, min_len=60)[sel])
                ok = cp in t
            print(f"  rung {rung:>2} {name:24s} U+{cp:04X} present={'YES' if ok else 'NO'}")
    for arc in TEXT_ARCS:
        q = Psarc(arc)
        vals = set(unc_loc.to_map(q.extract(_entry(q, "eng.common"))).values())
        print(f"  {os.path.relpath(arc, GAME)}: full={'YES' if any(PROBE_FULL in v for v in vals) else 'NO'}")


def main():
    ap = argparse.ArgumentParser(description="UNCHARTED LoT font-source sweep")
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
