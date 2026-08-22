#!/usr/bin/env python3
"""Reverse the THAI mod's own font work: decode the PhoenixFontDescriptorData resources
inside its DataPC_boot_patch_02.forge and parse them with the BFR GFOF model.
Tells us (a) whether descriptor override via patch_02 is a proven, shipping technique,
(b) exactly HOW the only person who solved this format edits it (grow vs repurpose)."""
import importlib.util, os, struct, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "tools")
INJ = os.path.join(HERE, "refmods", "injector", "oo2core_9_win64.dll")
os.environ["ACS_OODLE_DLL"] = INJ


def _load(n):
    p = os.path.join(TOOLS, n + ".py"); s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


AF = _load("acbf_forge"); CFD = _load("acbf_cfd")
sys.path.insert(0, os.path.join(HERE, "..", "..", "acshadows", "tools"))
from acs_oodle import Oodle

CLASS = 0xCBD4939A
REC, FH = 36, 32


def decode_record(f, r, oo):
    f.seek(r["offset"]); blob = f.read(r["size"])
    out = bytearray(); off = 0
    while off + 19 <= len(blob) and struct.unpack_from("<Q", blob, off)[0] == CFD.MAGIC:
        cnt = struct.unpack_from("<i", blob, off + 15)[0]
        bi = off + 19
        binfo = [struct.unpack_from("<ii", blob, bi + 8 * i) for i in range(cnt)]
        p = bi + cnt * 8
        for u, c in binfo:
            p += 4
            d = blob[p:p + c]; p += c
            out += d if c == u else oo.decompress(d, u)
        off = p
    return bytes(out)


def parse(buf):
    g = buf.find(b"GFOF")
    if g < 0:
        return None, []
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


for tag in ("th", "ua"):
    FN = os.path.join(HERE, "refmods", tag, "DataPC_boot_patch_02.forge")
    if not os.path.exists(FN):
        continue
    info = AF.parse(FN); recs = info["recs"]
    fonts = [(i, r) for i, r in enumerate(recs) if r["hash"] == CLASS]
    print("=" * 100)
    print("%s mod patch_02: %d records total, %d PhoenixFontDescriptorData" % (tag, len(recs), len(fonts)))
    print("   all classes: %s" % sorted({("%08x" % r["hash"]) for r in recs}))
    print("   fileIDs: %s" % ["%08x" % r["ts"] for r in recs])
    if not fonts:
        continue
    oo = Oodle(INJ)
    f = open(FN, "rb")
    for i, r in fonts:
        dec = decode_record(f, r, oo)
        out = os.path.join(HERE, "atlas", "%s_%d_%08x.bin" % (tag, i, r["ts"]))
        open(out, "wb").write(dec)
        g, faces = parse(dec)
        print("   idx %d fileID=%08x ondisk=%d decoded=%d GFOF@%s faces=%s"
              % (i, r["ts"], r["size"], len(dec), hex(g) if g else None, [x["cnt"] for x in faces]))
        if not faces:
            continue
        allr = sorted([x for fa in faces for x in fa["recs"]], key=lambda x: x[8])
        breaks = sum(1 for a, b in zip(allr, allr[1:]) if a[8] + int(a[6]) * int(a[7]) != b[8])
        end = g + allr[-1][8] + int(allr[-1][6]) * int(allr[-1][7])
        cps = [x[0] for x in allr]
        thai = sum(1 for c in cps if 0x0E00 <= c <= 0x0E7F)
        heb = sum(1 for c in cps if 0x0590 <= c <= 0x05FF)
        lat = sum(1 for c in cps if c < 0x250)
        print("      glyphs=%d breaks=%d tail=%d | THAI=%d latin=%d hebrew=%d | hdr=%s"
              % (len(allr), breaks, len(dec) - end, thai, lat, heb,
                 struct.unpack_from("<I2f5I", dec, g + 4)))
        if thai:
            th = [x for x in allr if 0x0E00 <= x[0] <= 0x0E7F][:6]
            print("      sample thai recs: %s" % [(hex(x[0]), round(x[1], 2), int(x[6]), int(x[7])) for x in th])
    f.close()
