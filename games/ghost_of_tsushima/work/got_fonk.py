#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""got_fonk.py — codec for Ghost of Tsushima DC's REAL in-game font: the 64-byte
"FontGlyphs" records that live inside KCAP (.xpps) packages.

VERIFIED FACTS (run against the real game files, see notes/FONT_ATTEMPT3_FINDINGS.md):
  * The "fOnk"@0x156bff7 in game.sprig.texmeshman is NOT a font — it is coincidental
    bytes inside a BCn texture (7.41 bit/byte entropy, zero cp-ladders). REFUTED premise.
  * The real font = fixed 64-byte glyph records, cp stored as u32 at +0, ascending,
    terminated by a cp==0xffff sentinel, inside KCAP packages (m_lm_menu, core_common...).
  * TWO record layouts exist:
      RICH  (m_lm_menu / UI fonts): +8 u32==4, +62 u16==0xffff, +4 f32 metric,
            +46..+58 four f32 (colour, ~1,1,1,1), +20..+45 a FIXED 24-byte descriptor.
      CMAP  (core_common): near-all-zero records, +62 == cp, a codepoint->id map only.
  * THE GLYPH OUTLINES ARE EXTERNAL. Proven: in m_lm_menu 103 glyphs share only 41
    distinct +20..+45 blocks and 55 shape-different glyphs (space,M,W,l,i,m,N,O..Z)
    carry the *identical* 24-byte block -> a fixed 24-byte field cannot be a per-glyph
    outline. The real outlines live in a separate FontVerts vertex buffer (uncracked).

WHAT THIS CODEC DOES (lossless, tested):
  * find_rich_tables(data): locate every RICH 64-byte glyph table in a KCAP blob.
  * read_table(data, start): -> (records[list[bytes64]], cps[list[int]], end_off).
  * write_table(records): -> bytes (identity: read then write == original table bytes).
  * repurpose_same_size(data, start, slot_to_cp): change only the cp (+0 u32) of chosen
    slots, keeping every other byte and the FILE SIZE identical (no KCAP directory
    surgery). Used to inject codepoint-map entries with zero risk to the container.

WHAT IT CANNOT DO (the blocker, documented for attempt #4):
  * synthesize a NEW Hebrew glyph SHAPE — that needs the external FontVerts format
    (vertex struct + winding + per-record reference field) which is not yet cracked,
    and the Arabic-slot font table (the true Hebrew target) is not yet located.
"""
import os, sys, struct

GREC = 64
REC_C8 = 4          # u32 @ +8 (RICH constant)
REC_SENT = 0xffff   # cp sentinel


# ---------------------------------------------------------------- record helpers
def rec_cp(rec):
    return struct.unpack_from("<H", rec, 0)[0]


def is_rich_rec(data, p):
    """A RICH glyph record signature: cp hi-bytes 0, +8 u32==4, +62 u16==0xffff."""
    if p + GREC > len(data):
        return False
    if struct.unpack_from("<H", data, p + 2)[0] != 0:      # cp high half == 0
        return False
    if struct.unpack_from("<I", data, p + 8)[0] != REC_C8:
        return False
    if struct.unpack_from("<H", data, p + 62)[0] != REC_SENT:
        return False
    return True


def rec_descriptor(rec):
    """The fixed 24-byte geometry/descriptor field (+20..+43 inclusive is 24 B here we
    use the documented +22..+45 window is opaque; we treat +20..+44 for grouping)."""
    return bytes(rec[20:44])


def is_notdef(rec):
    """A glyph whose 24-byte descriptor is all-zero == notdef / empty (e.g. controls)."""
    return rec_descriptor(rec) == b"\x00" * 24


# ---------------------------------------------------------------- table find/read/write
def find_rich_tables(data, min_run=16):
    """Find every RICH 64-byte glyph table. A table is a maximal run of rich records
    with strictly-ascending cp, optionally ending in a cp==0xffff sentinel record.
    Returns list of (start_off, cps, end_off)."""
    n = len(data)
    tables = []
    # prefilter: a rich record has bytes '04 00 00 00' at +8; candidate start = q-8.
    i = 0
    starts = []
    b = data
    # scan for the '04 00 00 00' pattern; cheap enough with bytes.find
    pos = b.find(b"\x04\x00\x00\x00")
    while pos != -1:
        p = pos - 8
        if p >= 0 and is_rich_rec(b, p):
            starts.append(p)
        pos = b.find(b"\x04\x00\x00\x00", pos + 1)
    used = set()
    for p in starts:
        if p in used:
            continue
        cp = rec_cp(b[p:p + GREC] if p + GREC <= n else b"\x00" * GREC)
        # only treat as a START if the previous 64 bytes are not an ascending rich rec
        if p - GREC >= 0 and is_rich_rec(b, p - GREC) and rec_cp(b[p - GREC:p]) == cp - 1:
            continue
        cps = []
        q = p
        while q + GREC <= n and is_rich_rec(b, q):
            c = rec_cp(b[q:q + GREC])
            if c == REC_SENT:
                used.add(q)
                q += GREC
                break
            if cps and c <= cps[-1]:
                break
            cps.append(c)
            used.add(q)
            q += GREC
        if len(cps) >= min_run:
            tables.append((p, cps, q))
    return tables


def read_table(data, start):
    """Read a RICH table starting at `start`. Returns (records, cps, end_off) where
    records is a list of 64-byte bytes objects INCLUDING the trailing sentinel record
    (if present). Stops at the sentinel or the first non-rich / non-ascending record."""
    n = len(data)
    records = []
    cps = []
    q = start
    while q + GREC <= n and is_rich_rec(data, q):
        rec = data[q:q + GREC]
        c = rec_cp(rec)
        if c == REC_SENT:
            records.append(rec)          # keep the sentinel record
            q += GREC
            break
        if cps and c <= cps[-1]:
            break
        records.append(rec)
        cps.append(c)
        q += GREC
    return records, cps, q


def write_table(records):
    """Concatenate records back to bytes. Identity: write_table(read_table(...)[0])
    reproduces the on-disk table byte-for-byte."""
    return b"".join(records)


# ---------------------------------------------------------------- same-size injection
def repurpose_same_size(data, start, slot_to_cp):
    """Change ONLY the cp (u32 @ +0) of selected table slots. `slot_to_cp` maps a
    slot index (0-based within the table's glyph records, excluding the sentinel) to a
    NEW codepoint. Every other byte is preserved and len(out)==len(data) (no KCAP
    directory surgery needed). The caller is responsible for keeping the table ASCENDING
    (the engine binary-searches cp) — repurposing the HIGHEST slots to even-higher cps
    (e.g. Latin<=0x86 slots -> Hebrew 0x5d0..0x5ea) preserves ascending order."""
    records, cps, end = read_table(data, start)
    out = bytearray(data)
    for slot, new_cp in slot_to_cp.items():
        recoff = start + slot * GREC
        struct.pack_into("<I", out, recoff, new_cp)   # cp is u32 (low u16 = cp, hi = 0)
    assert len(out) == len(data)
    return bytes(out)


# ---------------------------------------------------------------- CLI (inspection)
def _get_from_psarc(archive, name):
    GAME = os.environ.get("GOT_GAME", r"F:/Games/Ghost of Tsushima DC")
    PD = os.path.join(GAME, "cache_pc", "psarc")
    HERE = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(HERE, "..", "..", "tlou2", "tools"))
    import dsar as R
    arc = R.Psarc2(os.path.join(PD, archive))
    tgt = next((e for e in arc.files() if e.path.rstrip("/").endswith(name)), None)
    d = arc.extract(tgt) if tgt else None
    arc.d.f.close()
    return d


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "tables":
        data = _get_from_psarc(sys.argv[2], sys.argv[3])
        tbls = find_rich_tables(data)
        print(f"{sys.argv[3]}: {len(data):,}B  {len(tbls)} RICH glyph tables")
        for s, cps, e in sorted(tbls, key=lambda t: -len(t[1]))[:20]:
            print(f"  @0x{s:x} n={len(cps)} cp[0x{min(cps):x}..0x{max(cps):x}]")
    else:
        print(__doc__)
