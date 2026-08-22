#!/usr/bin/env python3
r"""
got_dsar.py — FAITHFUL DSAR writer for Ghost of Tsushima DC (Sucker Punch / Nixxes).

The generic games/tlou2/tools/dsar_write.py produces a DSAR our reader accepts but the GoT
ENGINE rejects (boot crash 2026-07-07). Measured deltas of the shipping GoT DSAR that
dsar_write.py got wrong (from cache_pc/psarc/gapack_misc_p.psarc):
  * reserved filler after compType = **`55 55 55 55 55 55 55`** (dsar_write used `54 55*6`).
  * every chunk compOffset is **16-byte aligned**; inter-chunk gaps are padded with the
    repeating ASCII pattern **"PADDING*"** (the same 8 bytes as the 0x18 header pad),
    truncated to the gap length (dsar_write packed contiguously, unaligned).
  * chunks are LZ4 (compType=3); the shipping chunker cuts at inner-content boundaries
    (variable, ≤256 KB), not fixed 256 KB. We can preserve the ORIGINAL boundaries for an
    identity/surgical rebuild, or fall back to fixed 256 KB.
Header + 32-byte entry layout are the same as tools/dsar.py documents.

    wrap(inner, boundaries=None) -> DSAR bytes
        boundaries = sorted list of chunk START offsets into the inner stream (0 first).
                     None => fixed 256 KB chunks.
    chunk_boundaries(dsar_path) -> the shipping chunk starts (to preserve on rebuild).
"""
import os, sys, struct
import lz4.block

CHUNK = 0x40000                       # 256 KB cap (matches shipping max uncompSize)
FILLER = b"\x55" * 7                  # GoT reserved filler (NOT tlou2's 54 55*6)
PAD_PAT = b"PADDING*"                 # 16-byte-alignment gap filler (repeating, truncated)
COMP_LZ4 = 3


def _pad_to_16(out):
    """Append PADDING* bytes until len(out) % 16 == 0."""
    gap = (-len(out)) % 16
    if gap:
        out += (PAD_PAT * ((gap // len(PAD_PAT)) + 1))[:gap]


def chunk_boundaries(dsar_path):
    """Return the shipping DSAR's chunk START offsets (decompOffset column)."""
    d = open(dsar_path, "rb").read(0x20)
    ne = struct.unpack_from("<I", d, 8)[0]
    with open(dsar_path, "rb") as f:
        f.seek(0x20); tbl = f.read(ne * 32)
    return [struct.unpack_from("<q", tbl, i * 32)[0] for i in range(ne)]


def wrap(inner: bytes, boundaries=None) -> bytes:
    if boundaries is None:
        boundaries = list(range(0, len(inner), CHUNK)) or [0]
    boundaries = sorted(set(b for b in boundaries if 0 <= b < len(inner))) or [0]
    ranges = []
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(inner)
        # never exceed the 256 KB cap even if the source boundary is wider
        while end - start > CHUNK:
            ranges.append((start, start + CHUNK)); start += CHUNK
        ranges.append((start, end))
    n = len(ranges)
    data_start = 0x20 + n * 32          # 0x20 + n*32 is always 16-aligned
    entries, payloads = [], bytearray()
    coff = data_start
    for start, end in ranges:
        raw = inner[start:end]; us = len(raw)
        comp = lz4.block.compress(raw, store_size=False)
        if comp is not None and len(comp) < us:
            payload, cs, ct = comp, len(comp), COMP_LZ4
        else:
            payload, cs, ct = raw, us, 0
        entries.append((start, coff, us, cs, ct))
        payloads += payload
        # 16-byte align the NEXT chunk's compOffset with PADDING* filler
        gap = (-(coff + cs)) % 16
        if gap:
            payloads += (PAD_PAT * 2)[:gap]
        coff += cs + gap

    out = bytearray()
    out += b"DSAR" + struct.pack("<HH", 3, 1)
    out += struct.pack("<I", n) + struct.pack("<I", data_start)
    out += struct.pack("<Q", len(inner))
    out += PAD_PAT                       # header 0x18..0x20
    assert len(out) == 0x20, len(out)
    for doff, coff_, us, cs, ct in entries:
        out += struct.pack("<qqii", doff, coff_, us, cs) + bytes([ct]) + FILLER
    assert len(out) == data_start, (len(out), data_start)
    out += payloads
    return bytes(out)


def patch_inner(src_path, out_path, edits, _reader=None):
    r"""SURGICAL same-size DSAR edit. edits = [(inner_off, new_bytes), ...] where each
    replaces exactly len(new_bytes) bytes at inner_off (the reconstructed inner-stream
    offset). Only DSAR chunks overlapping an edit are decompressed + re-LZ4'd; every other
    chunk's compressed payload is copied VERBATIM (byte-identical to shipping). The header
    (totalUncomp, numEntries, dataStart) is unchanged (same-size => nothing shifts inner-side).
    Returns (num_chunks_changed, out_size). Low-RAM: only changed chunks held in memory."""
    import importlib.util
    if _reader is None:
        HERE = os.path.dirname(os.path.abspath(__file__))
        REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
        spec = importlib.util.spec_from_file_location("dsar", os.path.join(REPO, "games", "tlou2", "tools", "dsar.py"))
        _reader = importlib.util.module_from_spec(spec); spec.loader.exec_module(_reader)
    R = _reader
    ps = R.Psarc2(src_path)
    D = ps.d
    n = D.num_entries
    d_off, c_off, u_size, c_size = D.d_off, D.c_off, D.u_size, D.c_size
    # compType + filler live in each 32-byte entry at +24; re-read them
    with open(src_path, "rb") as f:
        f.seek(0x20); etbl = f.read(n * 32)
    ctype = [etbl[i * 32 + 24] for i in range(n)]
    hdr = open(src_path, "rb").read(0x20)          # DSAR header (unchanged)
    data_start = struct.unpack_from("<I", hdr, 0x0C)[0]
    # which chunks overlap an edit?
    changed = {}                                    # idx -> new decompressed bytes
    for (o, nb) in edits:
        ln = len(nb)
        for i in range(n):
            cs_start, cs_end = d_off[i], d_off[i] + u_size[i]
            if o < cs_end and o + ln > cs_start:    # overlap
                if i not in changed:
                    changed[i] = bytearray(D.read(cs_start, u_size[i]))  # original inner bytes of this chunk
                lo = max(o, cs_start); hi = min(o + ln, cs_end)
                changed[i][lo - cs_start:hi - cs_start] = nb[lo - o:hi - o]
    # recompute payloads (compressed) + new c_size for changed; copy verbatim for the rest
    new_c_size = list(c_size)
    new_payload = {}                                # idx -> compressed bytes (only changed)
    for i, raw in changed.items():
        raw = bytes(raw)
        comp = lz4.block.compress(raw, store_size=False)
        if comp is not None and len(comp) < len(raw):
            new_payload[i] = comp; new_c_size[i] = len(comp); ctype[i] = COMP_LZ4
        else:
            new_payload[i] = raw; new_c_size[i] = len(raw); ctype[i] = 0
    # recompute 16-aligned c_offs for ALL chunks (verbatim ones move if an earlier chunk resized)
    new_c_off = [0] * n
    pos = data_start
    for i in range(n):
        new_c_off[i] = pos
        pos += new_c_size[i]
        pos += (-pos) % 16                          # 16-byte align next chunk
    total_out = pos
    # write: header + entry table + payloads (streamed; copy unchanged verbatim from src)
    with open(src_path, "rb") as src, open(out_path, "wb") as out:
        out.write(hdr)
        for i in range(n):
            out.write(struct.pack("<qqii", d_off[i], new_c_off[i], u_size[i], new_c_size[i]))
            out.write(bytes([ctype[i]]) + FILLER)
        assert out.tell() == data_start, (out.tell(), data_start)
        for i in range(n):
            assert out.tell() == new_c_off[i], (i, out.tell(), new_c_off[i])
            if i in new_payload:
                out.write(new_payload[i])
            else:
                src.seek(c_off[i]); out.write(src.read(c_size[i]))   # verbatim
            gap = (-out.tell()) % 16
            if gap:
                out.write((PAD_PAT * 2)[:gap])
    try: D.f.close()
    except Exception: pass
    return len(changed), total_out


def _selftest():
    """Rebuild gapack_misc_p preserving boundaries; verify it re-reads identically."""
    HERE = os.path.dirname(os.path.abspath(__file__))
    REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
    sys.path.insert(0, os.path.join(REPO, "games", "tlou2", "tools"))
    import dsar as R
    src = r"F:/Games/Ghost of Tsushima DC/cache_pc/psarc/gapack_misc_p.psarc"
    ps = R.Psarc2(src)
    inner = ps.d.read(0, ps.d.total_size)          # the full reconstructed inner stream
    bnds = chunk_boundaries(src)
    rebuilt = wrap(inner, bnds)
    import tempfile
    p = os.path.join(tempfile.gettempdir(), "_got_dsar_test.psarc")
    open(p, "wb").write(rebuilt)
    ps2 = R.Psarc2(p)
    a = {e.path: ps2.extract(e) for e in ps2.files()}
    b = {e.path: ps.extract(e) for e in ps.files()}
    ok = a == b
    # structural checks vs the original
    import struct as S
    o0 = S.unpack_from("<I", open(src, "rb").read(0x20), 8)[0]
    print(f"got_dsar identity rebuild: files-equal={ok}  chunks orig={o0} rebuilt={S.unpack_from('<I', rebuilt, 8)[0]}")
    print(f"  filler ok={rebuilt[0x39:0x40] == FILLER}  all-compOff-16aligned="
          f"{all(S.unpack_from('<q', rebuilt, 0x20 + i*32 + 8)[0] % 16 == 0 for i in range(S.unpack_from('<I', rebuilt, 8)[0]))}")
    try: ps2.d.f.close(); os.remove(p)
    except OSError: pass
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        sys.exit(_selftest())
    print(__doc__)
