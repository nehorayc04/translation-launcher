#!/usr/bin/env python3
"""Decode the THAI mod's PhoenixFontDescriptorData with the pure-python LZO1X path and
parse it with the BFR GFOF model. This reads the only known third-party-authored file of
this format -- i.e. it white-boxes the technique its author refuses to publish."""
import importlib.util, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "tools")
sys.path.insert(0, HERE)

def lz4_block(src):
    out = bytearray(); i = 0; n = len(src)
    while i < n:
        tok = src[i]; i += 1
        ll = tok >> 4
        if ll == 15:
            while True:
                b = src[i]; i += 1; ll += b
                if b != 255: break
        out += src[i:i + ll]; i += ll
        if i >= n: break
        off = src[i] | (src[i + 1] << 8); i += 2
        ml = tok & 15
        if ml == 15:
            while True:
                b = src[i]; i += 1; ml += b
                if b != 255: break
        ml += 4
        st = len(out) - off
        for k in range(ml): out.append(out[st + k])
    return bytes(out)



def _load(n):
    p = os.path.join(TOOLS, n + ".py"); s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


AF = _load("acbf_forge"); CFD = _load("acbf_cfd")
REC, FH = 36, 32


def decode(fn, want):
    info = AF.parse(fn); recs = info["recs"]
    f = open(fn, "rb")
    for i, r in enumerate(recs):
        if r["hash"] != 0xCBD4939A or r["ts"] != want:
            continue
        f.seek(r["offset"]); blob = f.read(r["size"])
        out = bytearray(); off = 0
        while off + 19 <= len(blob) and struct.unpack_from("<Q", blob, off)[0] == CFD.MAGIC:
            cnt = struct.unpack_from("<i", blob, off + 15)[0]
            bi = off + 19
            binfo = [struct.unpack_from("<ii", blob, bi + 8 * k) for k in range(cnt)]
            p = bi + cnt * 8
            for u, c in binfo:
                p += 4
                d = blob[p:p + c]; p += c
                out += d if c == u else lz4_block(d)
            off = p
        f.close()
        return bytes(out)
    f.close()
    return None


def parse(buf):
    g = buf.find(b"GFOF")
    faces, p = [], g + 36
    while True:
        cnt = struct.unpack_from("<I", buf, p)[0]
        if cnt > 20000 or buf[p + 4:p + 20] != b"\0" * 16:
            break
        upem, z, one = struct.unpack_from("<IIf", buf, p + 20)
        if upem not in (1000, 1024) or z or one != 1.0:
            break
        faces.append(dict(cnt=cnt, upem=upem,
                          recs=[struct.unpack_from("<I7fI", buf, p + FH + i * REC) for i in range(cnt)]))
        p += FH + cnt * REC
    return g, faces


for fid, base in ((0x88C2952A, "16243_88c2952a.bin"), (0x88C2952C, "16248_88c2952c.bin")):
    dec = decode(os.path.join(HERE, "refmods", "th", "DataPC_boot_patch_02.forge"), fid)
    print("=" * 100)
    if dec is None:
        print("fileID %08x not found" % fid); continue
    open(os.path.join(HERE, "atlas", "TH_%08x.bin" % fid), "wb").write(dec)
    print("THAI %08x decoded=%d bytes (vanilla counterpart: %s)" % (fid, len(dec), base))
    g, faces = parse(dec)
    hdr = struct.unpack_from("<I2f5I", dec, g + 4)
    allr = sorted([r for f in faces for r in f["recs"]], key=lambda r: r[8])
    breaks = sum(1 for a, b in zip(allr, allr[1:]) if a[8] + int(a[6]) * int(a[7]) != b[8])
    end = g + allr[-1][8] + int(allr[-1][6]) * int(allr[-1][7])
    cps = [r[0] for r in allr]
    rng = [("Latin", 0x20, 0x24F), ("Cyril", 0x400, 0x52F), ("THAI", 0xE00, 0xE7F),
           ("HEBREW", 0x590, 0x5FF), ("CJK", 0x2E80, 0x9FFF)]
    print("   GFOF@0x%x hdr=%s" % (g, hdr))
    print("   faces=%s  glyphs=%d  chainbreaks=%d  tail=%d" % ([f["cnt"] for f in faces], len(allr), breaks, len(dec) - end))
    print("   scripts: %s" % {n: sum(1 for c in cps if lo <= c <= hi) for n, lo, hi in rng})
    th = [r for r in allr if 0xE00 <= r[0] <= 0xE7F]
    if th:
        print("   thai sample: %s" % [(hex(r[0]), round(r[1], 2), int(r[6]), int(r[7])) for r in th[:8]])
        # SDF calibration of the THIRD-PARTY author's rasters vs ours
        import collections
        dc = collections.Counter()
        vals = collections.Counter()
        for r in th[:200]:
            W, H = int(r[6]), int(r[7])
            bm = dec[g + r[8]:g + r[8] + W * H]
            vals.update(bm)
            for y in range(0, H, 3):
                row = bm[y * W:(y + 1) * W]
                for a, b in zip(row, row[1:]):
                    if a and b:
                        dc[abs(a - b)] += 1
        print("   thai raster |delta| modes: %s ; max value=%d ; zeros=%.0f%%"
              % (dc.most_common(5), max(vals), 100 * vals[0] / sum(vals.values())))
