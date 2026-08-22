#!/usr/bin/env python3
"""Unified per-forge font/UI scanner (decompress once per resource, size-capped).
Reports: embedded sfnt fonts (family+Hebrew), FireData(SWF) resources, Scaleform SWF/GFX
magics. One hit line per finding. Designed to run per-forge in a parallel workflow."""
import sys, struct, json, io
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\tools")
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\work")
import acu_forge as F, acu_loc as L
from fontTools.ttLib import TTFont
try:
    reg = json.load(open(r"C:/tmp/acuwork/classreg.json"))
except Exception:
    reg = {}
FIREDATA = 2940455555
KNOWN = {b"cmap", b"glyf", b"head", b"hhea", b"hmtx", b"loca", b"maxp", b"name",
         b"post", b"OS/2", b"CFF ", b"GSUB", b"GPOS", b"cvt ", b"fpgm", b"prep", b"gasp"}
SWF_MAGICS = [b"FWS", b"CWS", b"ZWS", b"GFX", b"CFX", b"UEF"]
CAP = int(sys.argv[2]) * 1024 * 1024 if len(sys.argv) > 2 else 20 * 1024 * 1024


def all_cfd(blob):
    out = bytearray(); pos = 0; n = len(blob)
    while pos + 8 <= n and struct.unpack_from("<Q", blob, pos)[0] == L._MAGIC:
        try:
            nxt, dec = L.cfd_decompress(blob, pos)
        except Exception:
            break
        out += dec; pos = nxt
    return bytes(out)


def carve(dec):
    out = []
    for magic in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        k = 0
        while True:
            j = dec.find(magic, k)
            if j < 0:
                break
            k = j + 1
            if j + 12 > len(dec):
                continue
            numt = struct.unpack_from(">H", dec, j + 4)[0]
            if not (2 <= numt <= 40):
                continue
            good = 0; end = 0; ok = True
            for t in range(numt):
                ro = j + 12 + t * 16
                if ro + 16 > len(dec):
                    ok = False; break
                tag = dec[ro:ro + 4]
                off = struct.unpack_from(">I", dec, ro + 8)[0]
                ln = struct.unpack_from(">I", dec, ro + 12)[0]
                if tag in KNOWN:
                    good += 1
                end = max(end, off + ln)
            if not ok or good < 4 or end <= 0 or j + end > len(dec) + 4:
                continue
            try:
                ft = TTFont(io.BytesIO(dec[j:j + end]), lazy=True, fontNumber=0)
                fam = ft["name"].getDebugName(1) or ""
                cmap = ft.getBestCmap()
                heb = sum(1 for c in range(0x05D0, 0x05EB) if c in cmap)
                out.append((j, end, fam, heb, len(cmap)))
            except Exception:
                pass
    return out


def swf_hits(dec):
    hits = []
    for m in SWF_MAGICS:
        j = dec.find(m)
        while j >= 0:
            if j + 8 <= len(dec):
                ver = dec[j + 3]; flen = struct.unpack_from("<I", dec, j + 4)[0]
                rem = len(dec) - j
                if 1 <= ver <= 40 and 300 <= flen <= rem + 64 and flen >= rem - 65536:
                    hits.append((m.decode(), j, flen)); break
            j = dec.find(m, j + 1)
    return hits


def main():
    path = sys.argv[1]
    tag = path.replace("\\", "/").split("/")[-1]
    try:
        fg = F.Forge(path)
    except Exception as e:
        print(f"# {tag}: OPEN-FAIL {e}", flush=True); return
    nf = 0
    for i in range(fg.count):
        if fg.recs[i][0] == 0:
            continue
        ds = fg.disk_size(i)
        if ds < 400 or ds > CAP:
            continue
        try:
            blob = fg.extract_index(i)
            if struct.unpack_from("<Q", blob, 0)[0] != L._MAGIC:
                continue
            dec = all_cfd(blob)
        except Exception:
            continue
        if len(dec) < 8:
            continue
        cls_h = struct.unpack_from("<I", dec, 0)[0]
        cls = reg.get(str(cls_h), hex(cls_h))
        fonts = carve(dec)
        sw = swf_hits(dec)
        fd = (cls_h == FIREDATA)
        if fonts or sw or fd:
            nm = fg.index_to_name.get(i, "")
            fdesc = [f"{fam}:heb{heb}" for _o, _e, fam, heb, _n in fonts]
            print(f"HIT {tag} [{i}] cls={cls} FireData={fd} swf={sw} fonts={fdesc} disk={ds} name={nm}", flush=True)
            nf += 1
    print(f"# {tag}: hits={nf} count={fg.count}", flush=True)


if __name__ == "__main__":
    main()
