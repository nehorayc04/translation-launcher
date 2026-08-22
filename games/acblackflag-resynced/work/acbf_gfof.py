#!/usr/bin/env python3
"""
acbf_gfof.py — read/write PhoenixFontDescriptorData (class 0xCBD4939A), the baked
glyph-atlas resource behind AC Black Flag Resynced's Arabic (and CJK/Latin) text.

Layout (verified on all 11 shipped atlases AND on a third-party mod's rebuilt atlas
that the game actually loads):

    0x00 u16 version=1 | 0x02 u32 fileID | 0x06 u32 fileType | 0x0A u32 dataSize
    0x14 u32 classHash 0xCBD4939A | 0x18 u32 recSize | 0x1C u32 nameLen
    0x20 byte[nameLen] name ... "PHXFD" ... "GFOF"
    nend+51 u32 innerSize                             (nend = 0x20 + nameLen)

    GFOF+0x00 'GFOF' | +0x04 u32 3334 | +0x08 f32 ascent | +0x0C f32 descent
    +0x10 u32 pixelSize(40) | +0x14 u32 1 | +0x18 f32 0.2 | +0x1C u32 8 | +0x20 u32 pad
    GFOF+0x24 -> chain of FACE blocks (a count==0 face is NOT a terminator)

    FACE  = [u32 count][16B zeros][u32 upem][u32 0][f32 1.0]   (32 bytes)
            followed by count x 36-byte records
    REC   = <I7fI> = codepoint, advance, x0,y0,x1,y1, W,H, bitmapOffset
            bitmapOffset is relative to the 'GFOF' offset;
            raster = buf[GFOF+off : GFOF+off + W*H]  — 8-bit SDF, row-major, no padding

    Three size fields must be re-derived after any edit:
        dataSize  @0x0A     = size - 20
        recSize   @0x18     = size - 0x21 - nameLen
        innerSize @nend+51  = size - 24 - (nend + 55)
    and the file ends with exactly 24 zero bytes.
"""
import os
import struct

REC = 36
FH = 32
TAIL = 24


def is_face_hdr(buf, p):
    if p + FH > len(buf):
        return None
    cnt = struct.unpack_from("<I", buf, p)[0]
    if cnt > 20000 or buf[p + 4:p + 20] != b"\0" * 16:
        return None
    upem, z, one = struct.unpack_from("<IIf", buf, p + 20)
    if upem not in (1000, 1024) or z != 0 or one != 1.0:
        return None
    return cnt, upem


def parse(buf):
    """-> dict(gfof, faces=[{off,cnt,upem,hdr,recs}], nameLen, tableEnd)"""
    g = buf.find(b"GFOF")
    if g < 0:
        raise ValueError("no GFOF magic")
    faces, p = [], g + 36
    while True:
        h = is_face_hdr(buf, p)
        if h is None:
            break
        cnt, upem = h
        recs = [struct.unpack_from("<I7fI", buf, p + FH + i * REC) for i in range(cnt)]
        if not all(r[0] <= 0x10FFFF and 0 <= r[6] < 4096 and 0 <= r[7] < 4096
                   and r[6] == int(r[6]) and r[7] == int(r[7]) for r in recs):
            break
        faces.append({"off": p, "cnt": cnt, "upem": upem,
                      "hdr": bytes(buf[p:p + FH]), "recs": recs})
        p += FH + cnt * REC
    return {"gfof": g, "faces": faces, "tableEnd": p,
            "nameLen": struct.unpack_from("<I", buf, 0x1C)[0]}


def raster(buf, gfof, rec):
    w, h, off = int(rec[6]), int(rec[7]), rec[8]
    return bytes(buf[gfof + off: gfof + off + w * h])


def build(buf, faces_recs, rasters):
    """Rebuild the resource.
       faces_recs: list per face of [rec tuples] (codepoint..W,H, offset ignored)
       rasters:    dict id(rec)->bytes, or a parallel list-of-lists of raster bytes
       Returns the new file bytes."""
    info = parse(buf)
    g = info["gfof"]
    prefix = bytes(buf[:g])                    # outer header + name + PHXFD
    gfof_hdr = bytes(buf[g:g + 36])

    table = bytearray()
    n_by_face = []
    for fi, recs in enumerate(faces_recs):
        hdr = bytearray(info["faces"][fi]["hdr"])
        struct.pack_into("<I", hdr, 0, len(recs))
        table += hdr
        table += b"\0" * (len(recs) * REC)     # placeholder, filled after offsets known
        n_by_face.append(len(recs))

    blob_rel = 36 + len(table)                 # first raster offset, relative to GFOF
    blob = bytearray()
    off = blob_rel
    # fill records with recomputed offsets
    pos = 0
    out_tbl = bytearray()
    for fi, recs in enumerate(faces_recs):
        hdr = bytearray(info["faces"][fi]["hdr"])
        struct.pack_into("<I", hdr, 0, len(recs))
        out_tbl += hdr
        for ri, r in enumerate(recs):
            data = rasters[fi][ri]
            w, h = int(r[6]), int(r[7])
            assert len(data) == w * h, f"raster {len(data)} != {w}x{h}"
            out_tbl += struct.pack("<I7fI", r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], off)
            blob += data
            off += w * h
    assert len(out_tbl) == len(table)

    out = bytearray(prefix + gfof_hdr + bytes(out_tbl) + bytes(blob) + b"\0" * TAIL)
    size = len(out)
    nameLen = info["nameLen"]
    nend = 0x20 + nameLen
    struct.pack_into("<I", out, 0x0A, size - 20)
    struct.pack_into("<I", out, 0x18, size - 0x21 - nameLen)
    struct.pack_into("<I", out, nend + 51, size - 24 - (nend + 55))
    return bytes(out)


def check(buf, label=""):
    """Re-parse and assert every structural invariant. Returns a summary dict."""
    info = parse(buf)
    g = info["gfof"]
    allr = sorted([r for f in info["faces"] for r in f["recs"]], key=lambda r: r[8])
    breaks = [(a, b) for a, b in zip(allr, allr[1:])
              if a[8] + int(a[6]) * int(a[7]) != b[8]]
    blob_bytes = sum(int(r[6]) * int(r[7]) for r in allr)
    span = (allr[-1][8] + int(allr[-1][6]) * int(allr[-1][7])) - allr[0][8]
    tail = len(buf) - (g + allr[-1][8] + int(allr[-1][6]) * int(allr[-1][7]))
    n = len(buf); nameLen = info["nameLen"]; nend = 0x20 + nameLen
    ok = {
        "breaks": len(breaks) == 0,
        "blob==sum(W*H)": blob_bytes == span,
        "tail==24": tail == TAIL,
        "dataSize": struct.unpack_from("<I", buf, 0x0A)[0] == n - 20,
        "recSize": struct.unpack_from("<I", buf, 0x18)[0] == n - 0x21 - nameLen,
        "innerSize": struct.unpack_from("<I", buf, nend + 51)[0] == n - 24 - (nend + 55),
    }
    heb = sum(1 for r in allr if 0x590 <= r[0] <= 0x5FF)
    if label:
        flags = " ".join(f"{k}={'OK' if v else 'FAIL'}" for k, v in ok.items())
        print(f"  {label}: {len(allr)} glyphs, Hebrew={heb}, faces={[f['cnt'] for f in info['faces']]}")
        print(f"      {flags}")
    return {"ok": all(ok.values()), "checks": ok, "glyphs": len(allr), "hebrew": heb}
