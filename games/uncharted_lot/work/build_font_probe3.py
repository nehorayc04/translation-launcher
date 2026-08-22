#!/usr/bin/env python3
r"""
build_font_probe3.py — PROOF #6: the font is IDENTIFIED; this proves the write path.

Proof #5 (charset fingerprint, no font file touched) came back with
    1e 2u 3n 4c  YES   5^ 6~ 7-  NO   8" 9. 10E 11TM  YES   12yo 13alef  NO
i.e. Latin-1 + U+0107 + the symbol block, but NO modifier letters, NO en-dash and NO
Cyrillic.  Measured against every font the game ships, that pattern `YYYYNNNYYYYNN`
matches EXACTLY FOUR faces and nothing else:

    flash1/fontlib.swf            id5  Albertus Medium            255
    flash1/fontlib-sceasia.swf    id5  Albertus Medium            256
    flash1/fontlib-universal.swf  id5  HeiT ASC Medium Regular  3,178
    flash1/fontlib-scej.swf       id4  SCEJ-Seurat ProN M       2,245

and `hud-fonts.bin` (the routing table inside `dc1.psarc`) lists **Albertus Medium
FIRST** — it is the default UI face.  Every `.iggy` face is excluded by its own charset
(`fontlib.iggy` = NNNYYYYYYYYNN, no Latin-1 at all), which is exactly why proof #3's
12 Iggy remaps could never have shown anything.  `fontlib.iggy` is NOT a compiled
`fontlib.swf`: the two ship completely different face sets.

## Why proof #4 patched the right file and still showed nothing

`plan_slot` picks any ORDER-SAFE index, and in every one of these faces that is
`U+058F` — whose outline is **35 bytes**, the exact size of `U+FEFF` (ZWNBSP) in the
same font.  35 B *is* the blank glyph (2 B in the CJK faces).  So the lookup may well
have succeeded while drawing nothing.  A blank donor and a missing codepoint are
indistinguishable from the outside.

## The fix, and why this build is decisive

`unc_swf.repoint()` points the order-safe slot's glyph offset at a **real** outline —
the Euro sign (150-190 B, unmistakable on screen) — while the code table stays sorted.
Two entries sharing one shape offset is legal, because a SWF shape record is
self-terminating.  Everything stays delta-0.

Each rung therefore reads: **"N EUR" instead of "N box"** names the live font.

    rung 1  fontlib.swf           id5  Albertus Medium   <- the primary suspect
    rung 2  fontlib.swf           id1  Cast-Bold
    rung 3  fontlib.swf           id4  Cast-Regular
    rung 4  fontlib.swf           id3  Arial Unicode MS
    rung 5  fontlib-universal.swf id5  HeiT ASC Medium
    rung 6  fontlib-universal.swf id7  Albertus Medium
    rung 7  fontlib-universal.swf id1  Cast Bold
    rung 8  fontlib-sceasia.swf   id5  Albertus Medium
    rung 9  fontlib-scej.swf      id4  SCEJ-Seurat ProN M

Plus one INDEPENDENT lookup-only control that needs no glyph at all: on the primary
face the trademark sign is moved to an unused neighbouring codepoint, so if that face
is live **`11TM` must VANISH**.  Two different signals, one launch — and if every rung
boxes AND the trademark survives, the `.swf` is not what the engine reads, which sends
the work to the Iggy glyph format instead of another file hunt.

    python build_font_probe3.py --deploy | --revert | --verify
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
os.environ.setdefault("TLOU_OODLE_DLL", os.path.join(GAME, "oo2core_9_win64.dll"))

from psarc import Psarc                     # noqa: E402
from psarc_write import repack              # noqa: E402
from oodle import Oodle                     # noqa: E402
import unc_loc                              # noqa: E402
import unc_backup                          # noqa: E402
import unc_swf                              # noqa: E402

MARKER = "ZZ-UNC-OK-ZZ"
SAFE_CP = 0x058F      # the order-safe slot present in every one of these faces
DONOR_CP = 0x20AC     # the Euro sign — a big, unmistakable outline (150-190 B)
CONTROL_CP = 0x2122   # trademark: moved to a free neighbour on the primary face

# (rung, swf, font id, face) — rung N renders the DONOR glyph when that font is live
PLAN = [
    (1, "fontlib.swf",           5, "Albertus Medium"),
    (2, "fontlib.swf",           1, "Cast-Bold"),
    (3, "fontlib.swf",           4, "Cast-Regular"),
    (4, "fontlib.swf",           3, "Arial Unicode MS"),
    (5, "fontlib-universal.swf", 5, "HeiT ASC Medium"),
    (6, "fontlib-universal.swf", 7, "Albertus Medium"),
    (7, "fontlib-universal.swf", 1, "Cast Bold"),
    (8, "fontlib-sceasia.swf",   5, "Albertus Medium"),
    (9, "fontlib-scej.swf",      4, "SCEJ-Seurat"),
]
CONTROL = ("fontlib.swf", 5)          # the primary face carries the vanish test

# rung N is written as the digit N followed by the Nth Hebrew letter, so the user
# reads a NUMBER rather than counting positions ([[measure-with-a-ladder]])
LETTERS = [0x05D0, 0x05D1, 0x05D2, 0x05D3, 0x05D4,
           0x05D5, 0x05D6, 0x05D7, 0x05D8]      # alef .. tet

PROBE_SHORT = " ".join(f"{r}{chr(LETTERS[r - 1])}" for r in range(1, 6))
PROBE_FULL = (PROBE_SHORT + "  " +
              " ".join(f"{r}{chr(LETTERS[r - 1])}" for r in range(6, 10)) +
              "   11\u2122")            # the vanish control rides on the same line

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


def build_flash(src_psarc):
    """-> ({entry path: new bytes}, report rows).

    For each rung: rename the order-safe slot to a Hebrew letter (code-table only), then
    give that slot a REAL outline by COPYING the Euro glyph's shape in (`insert_glyph`,
    which preserves offset-table monotonicity — the broken `repoint` did NOT and
    black-screened the game).  Every modified body is run through `unc_swf.validate()`
    before it is repacked, so a structural defect can never reach the game again.
    """
    p = Psarc(src_psarc)
    bodies, forms, rows = {}, {}, []
    for rung, swf, fid, face in PLAN:
        e = _entry(p, swf)
        if e.path not in bodies:
            bodies[e.path], forms[e.path] = unc_swf.decompress(p.extract(e))
        body = bodies[e.path]
        f = [x for x in unc_swf.fonts(body) if x["id"] == fid][0]
        dst = unc_swf.index_of(f, SAFE_CP)
        src = unc_swf.index_of(f, DONOR_CP)
        if dst is None or src is None:
            raise ValueError(f"{swf} id{fid}: missing U+{SAFE_CP:04X}/U+{DONOR_CP:04X}")
        cp = LETTERS[rung - 1]
        # 1. rename the order-safe slot; 2. splice a real Euro outline into it
        body, old = unc_swf.patch(body, f, dst, cp)
        body = unc_swf.insert_glyph(body, f, dst, src)      # f is still valid: patch left offsets intact
        bodies[e.path] = body
        rows.append((rung, swf, fid, face, dst, f["sizes"][dst], f["sizes"][src], old, cp))

    # the lookup-only vanish control on the primary face
    e = _entry(p, CONTROL[0])
    body = bodies[e.path]
    f = [x for x in unc_swf.fonts(body) if x["id"] == CONTROL[1]][0]
    free = unc_swf.free_code_above(f, CONTROL_CP)
    if free is None:
        raise ValueError("no free codepoint above U+2122 on the control face")
    body, _ = unc_swf.patch(body, f, unc_swf.index_of(f, CONTROL_CP), free)
    bodies[e.path] = body
    rows.append(("C", CONTROL[0], CONTROL[1], "vanish control", -1, 0, 0,
                 CONTROL_CP, free))

    # 🔴 STRUCTURAL GATE — never repack a body that fails validation (the black-screen guard)
    for path, body in bodies.items():
        probs = unc_swf.validate(body, where=f"{os.path.basename(path)} ")
        if probs:
            raise RuntimeError("STRUCTURAL DEFECT — refusing to deploy:\n  " + "\n  ".join(probs))

    return {k: unc_swf.recompress(v, forms[k]) for k, v in bodies.items()}, rows


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
    print("== proof #6: real-outline repoint on every fingerprint-matching face ==")
    fmap, rows = build_flash(_backup(FLASH_ARC))
    for rung, swf, fid, face, dst, dsz, ssz, old, cp in rows:
        if rung == "C":
            print(f"  ctrl     {swf:22s} id{fid:<3d} {face:18s} "
                  f"U+{old:04X} -> U+{cp:04X}  (11\u2122 must VANISH if live)")
        else:
            print(f"  rung {rung}   {swf:22s} id{fid:<3d} {face:18s} slot {dst:>4d} "
                  f"blank {dsz}B -> Euro {ssz}B, U+{old:04X} -> U+{cp:04X} {chr(cp)}")
    tmap, n = build_text(_backup(TEXT_ARCS[0]))
    print(f"\n  short: {PROBE_SHORT}\n  full : {PROBE_FULL}\n  text : {n} sid overrides")
    print("== repack + deploy ==")
    repack(FLASH_ARC + ".he_backup", fmap, FLASH_ARC, od)
    unc_backup.deploy_done(FLASH_ARC)
    print(f"  {os.path.basename(FLASH_ARC)}  {os.path.getsize(FLASH_ARC):,} B  ({len(fmap)} entries)")
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


def _shape_bytes(body, f, i):
    base = f["off_base"]; ct = f["code_off"] - base
    s = f["offs"][i]; e = f["offs"][i + 1] if i + 1 < f["n"] else ct
    return bytes(body[base + s:base + e])


def cmd_verify(_a):
    print("== verify (reading the DEPLOYED archives) ==")
    p = Psarc(FLASH_ARC)
    ok = True
    for rung, swf, fid, face in PLAN:
        body, _ = unc_swf.decompress(p.extract(_entry(p, swf)))
        f = [x for x in unc_swf.fonts(body) if x["id"] == fid][0]
        cp = LETTERS[rung - 1]
        i = unc_swf.index_of(f, cp)
        srt = f["codes"] == sorted(f["codes"])
        clean = not unc_swf.validate(body)                        # structural: monotonic offsets etc.
        # the slot now holds a COPY of the Euro outline (not an alias) — compare the bytes
        euro = _shape_bytes(body, f, unc_swf.index_of(f, DONOR_CP))
        drew = i is not None and _shape_bytes(body, f, i) == euro
        ok &= bool(i is not None and srt and clean and drew)
        print(f"  rung {rung} {swf:22s} id{fid:<3d} U+{cp:04X} present={'Y' if i is not None else 'N'} "
              f"has-Euro-shape={'Y' if drew else 'N'} sorted={'Y' if srt else 'N'} "
              f"struct={'ok' if clean else 'BAD'}")
    body, _ = unc_swf.decompress(p.extract(_entry(p, CONTROL[0])))
    f = [x for x in unc_swf.fonts(body) if x["id"] == CONTROL[1]][0]
    ctrl_gone = CONTROL_CP not in f["codes"]
    ok &= ctrl_gone
    print(f"  ctrl   U+{CONTROL_CP:04X} still present={'Y (BAD)' if not ctrl_gone else 'N (good)'}")
    for arc in TEXT_ARCS:
        q = Psarc(arc)
        vals = set(unc_loc.to_map(q.extract(_entry(q, "eng.common"))).values())
        print(f"  {os.path.relpath(arc, GAME)}: full={'YES' if any(PROBE_FULL in v for v in vals) else 'NO'}"
              f"  short={'YES' if PROBE_SHORT in vals else 'NO'}")
    print("  ALL CHECKS PASS" if ok else "  !! a rung did not apply")


def main():
    ap = argparse.ArgumentParser(description="UNCHARTED LoT — real-outline font probe")
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
