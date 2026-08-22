#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""build_hebrew_font.py — GoT DC Hebrew FONT injection (round-2 attempt #5).

HONEST OUTCOME: NO real Hebrew glyph was produced. The precondition ("FontVerts cracked")
is NOT met. This script REPRODUCES the evidence that the located "Arabic table"
(ghost_title.xpps) is a CODEPOINT MAP, not a glyph-shape/outline table, so there is nothing
to repoint at a Hebrew outline, and the real vector outlines are a hash-keyed / packed blob
that is not decodable from the KCAP data by signature analysis. See
notes/FONT_ATTEMPT5_FINDINGS.md for the full write-up + the exact blocker + deploy recipe.

It does NOT fake a font and does NOT modify any file under F:/Games/... . Run:
    python work/build_hebrew_font.py
Reads the cached ghost_title.bin if present, else extracts ghost_title.xpps from
gapack_misc_g.psarc via games/tlou2/tools/dsar.py.
"""
import os, sys, struct

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/c--Users-Nehoray-Cohen-Projects-Game-translator/a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad"
GAME = os.environ.get("GOT_GAME", r"F:/Games/Ghost of Tsushima DC")
GREC = 64
HEB = list(range(0x05D0, 0x05EB))   # 27 Hebrew letters


def sep(t):
    print("\n" + "=" * 74 + f"\n{t}\n" + "=" * 74)


def load_ghost_title():
    cp = os.path.join(CACHE, "ghost_title.bin")
    if os.path.exists(cp) and os.path.getsize(cp) > 1_000_000:
        return open(cp, "rb").read()
    sys.path.insert(0, os.path.join(HERE, "..", "..", "tlou2", "tools"))
    import dsar as R
    arc = R.Psarc2(os.path.join(GAME, "cache_pc", "psarc", "gapack_misc_g.psarc"))
    tgt = next((e for e in arc.files() if e.path.rstrip("/").endswith("ghost_title.xpps")), None)
    d = arc.extract(tgt)
    arc.d.f.close()
    try:
        open(cp, "wb").write(d)
    except OSError:
        pass
    return d


def u16(d, p): return struct.unpack_from("<H", d, p)[0]
def u32(d, p): return struct.unpack_from("<I", d, p)[0]
def f32(d, p): return struct.unpack_from("<f", d, p)[0]


def find_first_ascii_record(d, cp_target):
    for p in range(0x860000, 0x8f0000):
        if (u16(d, p) == cp_target and u16(d, p + 2) == 0
                and u16(d, p + 20) == 0xf8 and u16(d, p + 62) == 0xffff):
            return p
    return None


def main():
    d = load_ghost_title()
    assert d[:4] == b"KCAP", f"expected KCAP, got {d[:4]!r}"
    print(f"ghost_title.xpps: {len(d):,} B  magic=KCAP  (Arabic-slot multi-script package)")

    sep("PROOF 1 — the 64-byte records are a CODEPOINT MAP, not glyph shapes")
    A = find_first_ascii_record(d, 0x41)
    O = find_first_ascii_record(d, 0x4f)
    I = find_first_ascii_record(d, 0x69)
    print(f"  'A' @0x{A:x}   'O' @0x{O:x}   'i' @0x{I:x}")
    dAO = [k for k in range(GREC) if d[A + k] != d[O + k]]
    dAI = [k for k in range(GREC) if d[A + k] != d[I + k]]
    print(f"  differing bytes  A vs O: {dAO}   A vs i: {dAI}")
    print(f"  A/O/i shared fields: +14={u16(d, A+14)} +16={u16(d, A+16)} +18=0x{u16(d, A+18):x} "
          f"geom={[round(f32(d, A+22+4*j),1) for j in range(3)]}")
    proof1 = (dAO == [0] and dAI == [0])
    print(f"  => A/O/i differ ONLY in the codepoint (+0): {proof1}")
    print("     Distinct-shape letters with byte-identical records ⇒ this is a CMAP; the "
          "records carry NO per-glyph outline and NO editable outline pointer.")

    sep("PROOF 2 — the 27 Hebrew records already exist, but as fallback markers (tofu)")
    # locate the Hebrew sub-table record for alef
    alef = None
    for p in range(0x87c000, 0x882000):
        if (u16(d, p) == 0x5d0 and u16(d, p + 2) == 0
                and u16(d, p + 20) == 0xf8 and u16(d, p + 62) == 0xffff):
            alef = p
            break
    if alef:
        refs = set()
        for i, c in enumerate(HEB):
            p = alef + i * GREC
            if u16(d, p) == c:
                refs.add((u16(d, p + 14), u16(d, p + 16), u16(d, p + 18)))
        print(f"  Hebrew alef @0x{alef:x}; U+05D0..05EA present in the cmap.")
        print(f"  their (+14,+16,+18): {sorted(refs)}  geom(alef)="
              f"{[round(f32(d, alef+22+4*j),1) for j in range(3)]}")
        print("  Non-zero geom = a 'draw a 5-unit box at (x,y)' notdef marker ⇒ scattered boxes "
              "= the in-game tofu. The cmap slot is NOT the gate (Latin shares a ref too and renders).")

    sep("PROOF 3 — ghost_title is a TITLE-CARD asset; outlines are hash-keyed/packed (opaque)")
    # section dir @0x198
    p = 0x198
    secs = []
    while p + 12 <= 0x8000:
        fl, k, sz, of = u16(d, p), u16(d, p + 2), u32(d, p + 4), u32(d, p + 8)
        if fl != 0x10 or of == 0 or of >= len(d) or sz > len(d):
            break
        secs.append((k, sz, of)); p += 12
    print(f"  section dir @0x198: {len(secs)} sections; "
          f"kind18(hash-index)={[hex(o) for k,s,o in secs if k==18]} "
          f"kind3(glyph/style+packed)={[hex(o) for k,s,o in secs if k==3]}")
    # confirm not LZ4
    import lz4.block
    lz4_ok = False
    for k, sz, of in secs:
        if k in (3, 18):
            try:
                lz4.block.decompress(d[of:of + sz], uncompressed_size=sz * 6); lz4_ok = True
            except Exception:
                pass
    print(f"  kind3/kind18 raw-LZ4 decodable: {lz4_ok}  (False ⇒ packed/quantized or a different codec)")
    kf = d.find(b"keyframe(")
    print(f"  ASCII 'keyframe(' animation curves present in the asset: {kf != -1} "
          f"(@0x{kf:x})  + style names hero/young_hero/heroine  ⇒ animated title-card, not a font store")

    sep("RESULT")
    print("  built = FALSE. No Hebrew outline synthesised or injected (would be faking it).")
    print("  BLOCKER: FontVerts vertex encoding + record→vertex resolution unknown; the outline")
    print("           payload is hash-keyed + packed (not raw LZ4/zlib, not plain f32/i16).")
    print("  NEXT (see notes/FONT_ATTEMPT5_FINDINGS.md §4): disassemble the exe SFontData loader /")
    print("        GENERATE_QUAD tessellator, OR resolve the kind18 name-hash index + its section")
    print("        codec, OR find the true UI-font package via a CONTENT signature (not the cmap sig).")
    print("  Deploy recipe (ready once outlines can be written) — FONT_ATTEMPT5_FINDINGS.md §5:")
    print("        edit font .xpps → fix KCAP dir(@0x198)+trailer(@0x2c) if grown → got_dsar.patch_inner")
    print("        (same-size) / got_dsar.wrap (grown) → drop zzz_hebrew_font.psarc in cache_pc/psarc →")
    print("        Text Language = العربية.")
    return 0 if proof1 else 1


if __name__ == "__main__":
    sys.exit(main())
