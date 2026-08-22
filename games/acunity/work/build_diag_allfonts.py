#!/usr/bin/env python3
"""DIAGNOSTIC: inject Hebrew (David) into ALL embedded fonts in rec109 at once, delta-0
in-place (subset Latin+punct + add U+05D0-05EA, pad to each font's stored slot). If the menu
font is any embedded TTF, the Hebrew text (English loc slot) will render readable."""
import io, sys, struct
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\tools")
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\work")
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\anno1800\work")
sys.path.insert(0, r"C:\tmp\acuwork")
import acu_forge as F, acu_loc as L
from carve_fonts import carve, all_cfd
import cfd_partial
from fontTools.ttLib import TTFont
from fontTools import subset
import anno_font as AF

P = r"E:/Games/Assassin's Creed Unity/DataPC.forge"
KEEP = (set(range(0x20, 0x250)) | set(range(0x2000, 0x2070))
        | set(range(0x20A0, 0x20D0)) | set(range(0x2100, 0x2150)))
DROP = ["hdmx", "LTSH", "VDMX", "GPOS", "GSUB", "GDEF", "kern", "gasp", "morx", "mort"]
SRC = r"C:\Windows\Fonts\david.ttf"


def heb_font(orig_bytes, src):
    opt = subset.Options(recalc_bounds=False, recalc_timestamp=False,
                         glyph_names=True, notdef_outline=True, ignore_missing_glyphs=True,
                         ignore_missing_unicodes=True)
    opt.drop_tables += DROP
    ft = TTFont(io.BytesIO(orig_bytes), fontNumber=0)
    cov = set(ft.getBestCmap().keys())
    ss = subset.Subsetter(opt)
    ss.populate(unicodes=[c for c in KEEP if c in cov] or [0x41])
    ss.subset(ft)
    for t in DROP:
        if t in ft:
            del ft[t]
    AF._add_hebrew(ft, src)
    for t in DROP:
        if t in ft:
            del ft[t]
    b = io.BytesIO(); ft.save(b)
    return b.getvalue()


def main():
    fg = F.Forge(P)
    blob = fg.extract_index(fg.name_to_index["TGame Bootstrap Settings"])
    slot = fg.disk_size(fg.name_to_index["TGame Bootstrap Settings"])
    p1, _ = L.cfd_decompress(blob, 0)
    cfd_start, cfd_end, compinfo7, blocks = cfd_partial.parse_cfd(blob, p1)
    p2, content = L.cfd_decompress(blob, p1)
    sig = blob[p2:]
    content = bytearray(content)
    print(f"content={len(content):,} blocks={len(blocks)} sig={len(sig)}", flush=True)

    src = TTFont(SRC)
    fonts = carve(bytes(content))
    changed = []
    for off, size, fam, heb, latin, ncmap in fonts:
        stored = struct.unpack_from("<I", content, off - 4)[0]   # authoritative slot
        orig = bytes(content[off:off + stored])
        try:
            nt = heb_font(orig, src)
        except Exception as e:
            print(f"  !! {fam} inject failed: {e}", flush=True); continue
        if len(nt) > stored:
            print(f"  !! {fam}: {len(nt)} > slot {stored} — SKIP", flush=True); continue
        content[off:off + stored] = nt + b"\x00" * (stored - len(nt))
        changed.append((off, off + stored))
        r = TTFont(io.BytesIO(nt), lazy=True)
        h = sum(1 for c in range(0x05D0, 0x05EB) if c in r.getBestCmap())
        lat = sum(1 for c in range(0x41, 0x5B) if c in r.getBestCmap())
        print(f"  injected {fam:14} @0x{off:x} slot={stored:>9,} new={len(nt):>9,} heb={h}/27 lat={lat}/26", flush=True)

    print(f"changed {len(changed)} fonts; partial re-LZO ...", flush=True)
    newcfd2 = cfd_partial.rebuild_partial(compinfo7, blocks, content, changed)
    newdata = blob[:p1] + newcfd2 + sig
    print(f"new .data {len(newdata):,}  slot {slot:,}  fits={len(newdata) <= slot}", flush=True)
    outp = r"C:/tmp/acuwork/bootstrap_HE_all.data"
    open(outp, "wb").write(newdata)

    # verify
    q1, _ = L.cfd_decompress(newdata, 0)
    q2, c2 = L.cfd_decompress(newdata, q1)
    ok = 0
    for (off, end) in changed:
        ft = TTFont(io.BytesIO(bytes(c2[off:off + struct.unpack_from("<I", c2, off - 4)[0]])), lazy=True)
        if sum(1 for c in range(0x05D0, 0x05EB) if c in ft.getBestCmap()) == 27:
            ok += 1
    print(f"VERIFY rebuilt: content_len_same={len(c2)==len(content)} fonts_with_heb={ok}/{len(changed)}  -> {outp}", flush=True)


if __name__ == "__main__":
    main()
