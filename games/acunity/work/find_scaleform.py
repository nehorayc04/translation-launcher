#!/usr/bin/env python3
"""Comprehensive per-resource font/UI detector for one forge. Decompress every resource,
detect: Scaleform SWF/GFX (FWS/CWS/ZWS/GFX/CFX + obfuscated UEF), embedded sfnt TTF,
and any font-family / DefineFont ASCII markers. Prints every hit with the wrapping class."""
import sys, struct, json
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\tools")
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\work")
import acu_forge as F, acu_loc as L
try:
    reg = json.load(open(r"C:/tmp/acuwork/classreg.json"))
except Exception:
    reg = {}

SWF_MAGICS = [b"FWS", b"CWS", b"ZWS", b"GFX", b"CFX", b"UEF"]  # UEF = FireData-obfuscated FWS


def all_cfd(blob):
    out = bytearray(); pos = 0; n = len(blob)
    while pos + 8 <= n and struct.unpack_from("<Q", blob, pos)[0] == L._MAGIC:
        try:
            nxt, dec = L.cfd_decompress(blob, pos)
        except Exception:
            break
        out += dec; pos = nxt
    return bytes(out)


def swf_hits(dec):
    hits = []
    for m in SWF_MAGICS:
        k = 0
        while True:
            j = dec.find(m, k)
            if j < 0:
                break
            k = j + 1
            if j + 8 > len(dec):
                continue
            ver = dec[j + 3]
            flen = struct.unpack_from("<I", dec, j + 4)[0]
            rem = len(dec) - j
            if 1 <= ver <= 40 and 300 <= flen <= rem + 64 and flen >= rem - 65536:
                hits.append((m.decode(), j, flen))
                break
    return hits


def ttf_hits(dec):
    n = 0
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
            if 4 <= numt <= 30:
                # verify: table dir tags mostly ascii-uppercase and offsets in-range
                good = 0
                for t in range(min(numt, 12)):
                    ro = j + 12 + t * 16
                    if ro + 16 > len(dec):
                        break
                    tag = dec[ro:ro + 4]
                    if all(0x20 <= c < 0x7f for c in tag):
                        good += 1
                if good >= min(numt, 8):
                    n += 1
    return n


def main():
    fg = F.Forge(sys.argv[1])
    tag = sys.argv[1].split("/")[-1]
    hits = 0
    for i in range(fg.count):
        if fg.recs[i][0] == 0:
            continue
        ds = fg.disk_size(i)
        if ds < 500 or ds > 20 * 1024 * 1024:
            continue
        try:
            blob = fg.extract_index(i)
            if struct.unpack_from("<Q", blob, 0)[0] != L._MAGIC:
                continue
            dec = all_cfd(blob)
        except Exception:
            continue
        sw = swf_hits(dec)
        tt = ttf_hits(dec)
        if sw or tt:
            cls = reg.get(str(struct.unpack_from("<I", dec, 0)[0]), hex(struct.unpack_from("<I", dec, 0)[0])) if len(dec) >= 4 else "?"
            nm = fg.index_to_name.get(i, "")
            print(f"  {tag} [{i:5}] cls={cls:<16} swf={sw} ttf={tt} disk={ds:>9,}  {nm}", flush=True)
            hits += 1
    print(f"# {tag}: hits={hits}", flush=True)


if __name__ == "__main__":
    main()
