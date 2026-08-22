#!/usr/bin/env python3
"""Identify the codec the community BFR mods use for their forge chunks.
Candidates tried: LZ4 block, LZO1X (pure python port), zlib/raw-deflate."""
import importlib.util, os, struct, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "tools")
sys.path.insert(0, HERE)
import lzo1x


def _load(n):
    p = os.path.join(TOOLS, n + ".py"); s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


AF = _load("acbf_forge"); CFD = _load("acbf_cfd")


def lz4_block(src, want):
    out = bytearray()
    i = 0
    n = len(src)
    while i < n:
        tok = src[i]; i += 1
        ll = tok >> 4
        if ll == 15:
            while True:
                b = src[i]; i += 1
                ll += b
                if b != 255:
                    break
        out += src[i:i + ll]; i += ll
        if i >= n:
            break
        off = src[i] | (src[i + 1] << 8); i += 2
        if off == 0:
            raise ValueError("offset 0")
        ml = tok & 15
        if ml == 15:
            while True:
                b = src[i]; i += 1
                ml += b
                if b != 255:
                    break
        ml += 4
        start = len(out) - off
        if start < 0:
            raise ValueError("bad offset %d at out=%d" % (off, len(out)))
        for k in range(ml):
            out.append(out[start + k])
    return bytes(out)


fn = os.path.join(HERE, "refmods", "th", "DataPC_boot_patch_02.forge")
info = AF.parse(fn); recs = info["recs"]
f = open(fn, "rb")
r = [r for r in recs if r["hash"] == 0xCBD4939A][0]
f.seek(r["offset"]); blob = f.read(r["size"]); f.close()
off = 0
blocks = []
while off + 19 <= len(blob) and struct.unpack_from("<Q", blob, off)[0] == CFD.MAGIC:
    cnt = struct.unpack_from("<i", blob, off + 15)[0]
    bi = off + 19
    binfo = [struct.unpack_from("<ii", blob, bi + 8 * k) for k in range(cnt)]
    p = bi + cnt * 8
    for u, c in binfo:
        chk = struct.unpack_from("<I", blob, p)[0]; p += 4
        blocks.append((u, c, chk, blob[p:p + c])); p += c
    off = p
print("blocks: %s" % [(u, c) for u, c, _, _ in blocks][:14])
for idx, (u, c, chk, data) in enumerate(blocks):
    if u == c:
        print("  block%d RAW %d bytes head=%s" % (idx, u, data[:12].hex()))
        continue
    print("  block%d want=%d have=%d chk=%08x head=%s" % (idx, u, c, chk, data[:12].hex()))
    for name, fnc in (("lz4", lambda d: lz4_block(d, u)),
                      ("lzo1x", lambda d: lzo1x.decompress(d, u)),
                      ("zlib-raw", lambda d: zlib.decompressobj(-15).decompress(d)),
                      ("zlib", lambda d: zlib.decompress(d))):
        try:
            o = fnc(data)
            print("     %-9s -> %d bytes %s  head=%s" % (name, len(o), "MATCH" if len(o) == u else "size-mismatch", o[:16].hex()))
        except Exception as e:
            print("     %-9s -> FAIL %s" % (name, str(e)[:70]))
    if idx >= 2:
        break
