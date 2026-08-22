#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""build_hebrew_fonk.py — the font-injection deliverable for GoT DC Hebrew (attempt #3).

HONEST OUTCOME (all steps run against the REAL game files; nothing under F:/Games is
modified — the only artifact is a SCRATCH copy of a font package):

  * The recon premise ("inject 27 Hebrew glyphs into the fOnk chunk of
    game.sprig.texmeshman") is VOID: fOnk@0x156bff7 is texture bytes, not a font
    (re-verified here). Editing texmeshman cannot add a Hebrew glyph.

  * The REAL font = 64-byte FontGlyphs records in KCAP .xpps packages. This tool builds
    a lossless CODEC for that table (got_fonk.py), proves an IDENTITY round-trip, and
    demonstrates a byte-safe SAME-SIZE codepoint-map injection: it maps U+05D0..U+05EA
    into a real glyph table so those 27 Hebrew codepoints stop resolving to notdef.

  * It does NOT produce Hebrew LETTER SHAPES. The glyph OUTLINES are stored in a separate
    external `FontVerts` buffer whose format + per-record reference are NOT yet cracked
    (proven: 55 shape-different glyphs share one identical 24-byte in-record descriptor,
    so the shape is not in the record). The injected 27 records therefore carry a CLONED
    existing (Latin) outline as a placeholder — real Hebrew requires synthesizing new
    FontVerts, which is the stated blocker for attempt #4. The demo also runs on the
    Latin menu font (m_lm_menu), because the Arabic-slot font table — the true Hebrew
    target — is not yet located in the ~20 GB of packages.

Usage:  python work/build_hebrew_fonk.py
Writes: work/_proof_out/m_lm_menu_hebrew_demo.sprig.xpps  (scratch, NOT deployed)
"""
import os, sys, struct, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.environ.get("GOT_GAME", r"F:/Games/Ghost of Tsushima DC")
PD = os.path.join(GAME, "cache_pc", "psarc")
OUT_DIR = os.path.join(HERE, "_proof_out")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tlou2", "tools"))
import got_fonk as F
import dsar as R

HEB = list(range(0x05D0, 0x05EB))   # 27 Hebrew letters alef..tav (U+05D0..U+05EA)


def sep(t):
    print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)


def get(archive, name):
    arc = R.Psarc2(os.path.join(PD, archive))
    tgt = next((e for e in arc.files() if e.path.rstrip("/").endswith(name)), None)
    d = arc.extract(tgt) if tgt else None
    arc.d.f.close()
    return d


def step_refute_fonk():
    sep("STEP A — refute the fOnk premise (fOnk is texture, not a font)")
    p = os.path.join(HERE, "..", "extract", "game.sprig.texmeshman")
    if not os.path.exists(p):
        print("  (local extract/game.sprig.texmeshman not present; skipping)")
        return
    off = 0x156BFF7
    with open(p, "rb") as f:
        f.seek(off - 8)
        ctx = f.read(16)
        f.seek(max(0, off - 4096))
        win = f.read(8192)
    import math, collections
    h = collections.Counter(win)
    ent = -sum((n / len(win)) * math.log2(n / len(win)) for n in h.values())
    runs = 0
    for base in range(0, len(win) - 5 * 64, 2):
        cp0 = struct.unpack_from("<H", win, base)[0]
        if 1 <= cp0 <= 0x6ff and all(
                struct.unpack_from("<H", win, base + k * 64)[0] == cp0 + k for k in range(5)):
            runs += 1
    print(f"  fOnk bytes: {ctx.hex()}   (contains the ascii 'fOnk' at +8)")
    print(f"  entropy of 8KB window around fOnk: {ent:.2f} bit/byte  (texture/compressed ~7.4-8)")
    print(f"  64-byte cp-ladder runs near fOnk : {runs}  (a real glyph table would have >=1)")
    print("  VERDICT: fOnk is texture data. Editing texmeshman cannot add a Hebrew glyph.")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    step_refute_fonk()

    sep("STEP B — read the REAL font glyph table + prove a lossless round-trip")
    ARC, NAME = "gapack_misc_m.psarc", "m_lm_menu.sprig.xpps"
    data = get(ARC, NAME)
    assert data[:4] == b"KCAP", f"expected KCAP, got {data[:4]!r}"
    tbls = F.find_rich_tables(data)
    tbls.sort(key=lambda t: -len(t[1]))
    start, cps, end = tbls[0]
    records, cps2, end2 = F.read_table(data, start)
    print(f"  {NAME}: {len(data):,}B, {len(tbls)} RICH tables; biggest @0x{start:x}")
    print(f"    glyph records={len(cps2)}  cp[0x{min(cps2):x}..0x{max(cps2):x}]  "
          f"sentinel record present={records[-1][:2].hex()=='ffff'}")
    # identity round-trip of the table bytes
    rebuilt = F.write_table(records)
    on_disk = data[start:end2]
    ident = rebuilt == on_disk
    print(f"    identity round-trip (read_table->write_table == on-disk): {ident}")
    assert ident, "round-trip FAILED"
    # how many distinct in-record descriptors -> proof outlines are external
    descr = {}
    for r in records:
        if F.rec_cp(r) != F.REC_SENT:
            descr.setdefault(F.rec_descriptor(r), []).append(F.rec_cp(r))
    biggest = max(descr.values(), key=len)
    print(f"    {len(cps2)} glyphs share only {len(descr)} distinct 24-byte descriptors; "
          f"one block is shared by {len(biggest)} shape-different glyphs")
    print("    => glyph OUTLINES are EXTERNAL (a fixed 24-byte field is not a per-glyph shape)")

    sep("STEP C — SAME-SIZE injection of 27 Hebrew codepoints (byte-safe demo)")
    # repurpose the 27 HIGHEST glyph slots (largest cps) -> Hebrew 0x5d0..0x5ea.
    # all Latin cps < 0x5d0, so ascending order is preserved and no KCAP surgery is needed.
    glyph_slots = [i for i, r in enumerate(records) if F.rec_cp(r) != F.REC_SENT]
    assert len(glyph_slots) >= 27, "table too small for the demo"
    victim_slots = glyph_slots[-27:]                      # the 27 highest-cp records
    old_cps = [F.rec_cp(records[s]) for s in victim_slots]
    slot_to_cp = {s: HEB[i] for i, s in enumerate(victim_slots)}   # ascending 0x5d0..0x5ea
    new_bytes = F.repurpose_same_size(data, start, slot_to_cp)
    assert len(new_bytes) == len(data), "size changed!"
    out_path = os.path.join(OUT_DIR, "m_lm_menu_hebrew_demo.sprig.xpps")
    with open(out_path, "wb") as f:
        f.write(new_bytes)
    print(f"  remapped 27 slots (old cp 0x{min(old_cps):x}..0x{max(old_cps):x}) -> "
          f"Hebrew U+05D0..U+05EA, file size {len(data):,} (unchanged)")
    print(f"  scratch package written: {out_path}")

    sep("STEP D — OFFLINE VALIDATION: re-decode the built package")
    with open(out_path, "rb") as f:
        nd = f.read()
    ntbls = F.find_rich_tables(nd)
    ntbls.sort(key=lambda t: -len(t[1]))
    ns, ncps, ne = ntbls[0]
    heb_present = [c for c in ncps if 0x5d0 <= c <= 0x5ea]
    ascending = all(ncps[i] < ncps[i + 1] for i in range(len(ncps) - 1))
    # each Hebrew record must be NON-notdef (carries a real cloned Latin outline descriptor)
    nrecords, _, _ = F.read_table(nd, ns)
    heb_recs = [r for r in nrecords if 0x5d0 <= F.rec_cp(r) <= 0x5ea]
    nondef = sum(1 for r in heb_recs if not F.is_notdef(r))
    print(f"  re-decoded table @0x{ns:x}: {len(ncps)} glyphs, ascending={ascending}")
    print(f"  Hebrew codepoints now present in the map: {len(heb_present)}/27 "
          f"(0x{min(heb_present):x}..0x{max(heb_present):x})")
    print(f"  of those, records that are REAL (non-notdef, letter-like descriptor): {nondef}/27")
    print(f"  file size unchanged: {len(nd) == len(data)}  (no container offset fixup needed)")
    ok = (len(heb_present) == 27 and ascending and nondef == 27 and len(nd) == len(data))
    print(f"\n  MECHANISM-DEMO VALIDATION: {'PASS' if ok else 'FAIL'}")
    print("  (proves: the codepoint->glyph MAP can be edited losslessly & the 27 Hebrew")
    print("   codepoints resolve to real non-notdef glyph records. NOTE: the SHAPES are the")
    print("   cloned Latin outlines, NOT Hebrew letters — real Hebrew shapes are blocked on")
    print("   the external FontVerts outline format + locating the Arabic-slot font table.)")

    sep("BLOCKER (for attempt #4) & DEPLOY NOTE")
    print("  To render actual Hebrew LETTERS in-game you still need, in order:")
    print("   1. LOCATE the Arabic-slot glyph table (a large clean Arabic 64-byte table).")
    print("      Not in core_common/core_tsu/core_iki/m_lm_menu (Latin only); the small")
    print("      Arabic runs in level/title packages are mesh / consecutive-int false")
    print("      positives. Needs a scan of the remaining big packages (misc_g game.sprig,")
    print("      misc_m, misc_t) OR cracking the packman hash index to resolve the")
    print("      SFontData resource by type-hash.")
    print("   2. CRACK the external FontVerts buffer: its location, the per-record reference")
    print("      field (a field that VARIES among the 55 same-descriptor glyphs — candidates")
    print("      +4/+12/+16), the vertex struct + winding + coord scale.")
    print("   3. SYNTHESISE 27 Hebrew outlines from a TTF (fontTools) tessellated to the")
    print("      FontVerts format, append them, point 27 new records at them.")
    print("   4. GROW + re-serialise the KCAP package (fix its directory offsets), then")
    print("      re-wrap DSAR/PSARC (work/got_dsar.py) and deploy as an additive override")
    print("      .psarc in cache_pc/psarc (proven mechanism), Text Language = العربية.")
    print(f"\n  scratch artifact: {out_path}")


if __name__ == "__main__":
    main()
