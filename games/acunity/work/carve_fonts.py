#!/usr/bin/env python3
"""Carve valid sfnt TTFs from a decompressed resource. Validate each candidate by loading
its table directory (known tags) and, if fontTools loads it, report family + Hebrew coverage."""
import sys, struct, io
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\tools")
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\work")
import acu_forge as F, acu_loc as L
from fontTools.ttLib import TTFont

KNOWN = {b"cmap", b"glyf", b"head", b"hhea", b"hmtx", b"loca", b"maxp",
         b"name", b"post", b"OS/2", b"CFF ", b"GSUB", b"GPOS", b"cvt ",
         b"fpgm", b"prep", b"gasp"}


def all_cfd(blob):
    out = bytearray(); pos = 0; n = len(blob)
    while pos + 8 <= n and struct.unpack_from("<Q", blob, pos)[0] == L._MAGIC:
        nxt, dec = L.cfd_decompress(blob, pos)
        out += dec; pos = nxt
    return bytes(out)


def carve(dec):
    """Yield (offset, size, family, heb, latin) for each valid sfnt in dec."""
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
            # validate table directory: 16-byte records, tags mostly known, compute end
            good = 0; end = 0
            ok = True
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
            if not ok or good < 3 or end <= 0 or j + end > len(dec) + 4:
                continue
            size = end
            blob = dec[j:j + size]
            try:
                ft = TTFont(io.BytesIO(blob), lazy=True, fontNumber=0)
                fam = ""
                try:
                    fam = ft["name"].getDebugName(1) or ft["name"].getDebugName(4) or ""
                except Exception:
                    pass
                cmap = ft.getBestCmap()
                heb = sum(1 for c in range(0x05D0, 0x05EB) if c in cmap)
                latin = sum(1 for c in range(0x41, 0x5B) if c in cmap)
                out.append((j, size, fam, heb, latin, len(cmap)))
            except Exception:
                out.append((j, size, "<unloadable>", -1, -1, -1))
    return out


def main():
    fg = F.Forge(sys.argv[1])
    rec = int(sys.argv[2])
    blob = fg.extract_index(rec)
    dec = all_cfd(blob)
    nm = fg.index_to_name.get(rec, "")
    print(f"# rec {rec} '{nm}'  decompressed {len(dec):,} B")
    fonts = carve(dec)
    print(f"# carved {len(fonts)} valid sfnt fonts:")
    for off, size, fam, heb, latin, ncmap in fonts:
        print(f"  @0x{off:<8x} size={size:>8,}  heb={heb:>2}/27 latin={latin:>2}/26 cmap={ncmap:>4}  {fam!r}")


if __name__ == "__main__":
    main()
