#!/usr/bin/env python3
"""Build a Hebrew-font bootstrap .data for AC Unity: inject Hebrew (subset+merge) into
the 3 embedded News Gothic TTFs IN PLACE (padded to original size => content length
unchanged => delta-0), re-LZO the 113MB CFD2, reassemble the resource, verify, write."""
import io, sys, struct, os
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\tools")
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\work")
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\anno1800\work")
sys.path.insert(0, r"C:\tmp\acuwork")
import acu_forge as F, acu_loc as L
from fontTools.ttLib import TTFont
from fontTools import subset
import anno_font as AF
from acu_minbuild import make_cfd_lzo

P = r"E:\Games\Assassin's Creed Unity\DataPC.forge"
KEEP = (set(range(0x20, 0x250)) | set(range(0x2000, 0x2070))
        | set(range(0x20A0, 0x20D0)) | set(range(0x2100, 0x2150)))
DROP = ["hdmx", "LTSH", "VDMX", "GPOS", "GSUB", "GDEF", "kern", "gasp"]


def heb_font(orig_bytes, src):
    """subset News Gothic to Latin+punct + inject Hebrew; return bytes (<= orig)."""
    opt = subset.Options(recalc_bounds=False, recalc_timestamp=False,
                         glyph_names=True, notdef_outline=True)
    opt.drop_tables += DROP
    ft = TTFont(io.BytesIO(orig_bytes))
    cov = set(ft.getBestCmap().keys())
    ss = subset.Subsetter(opt)
    ss.populate(unicodes=[c for c in KEEP if c in cov])
    ss.subset(ft)
    for t in DROP:
        if t in ft:
            del ft[t]
    AF._add_hebrew(ft, src)
    for t in DROP:
        if t in ft:
            del ft[t]
    b = io.BytesIO()
    ft.save(b)
    return b.getvalue()


def main():
    fg = F.Forge(P)
    i = fg.name_to_index["TGame Bootstrap Settings"]
    blob = fg.extract_index(i)
    slot = fg.disk_size(i)
    print(f"bootstrap on-disk {len(blob):,}  slot {slot:,}", flush=True)
    p1, meta = L.cfd_decompress(blob, 0)
    import cfd_partial
    cfd_start, cfd_end, compinfo7, blocks = cfd_partial.parse_cfd(blob, p1)
    p2, content = L.cfd_decompress(blob, p1)
    sig = blob[p2:]
    content = bytearray(content)
    print(f"CFD1(meta)={p1}  CFD2 content={len(content):,}  blocks={len(blocks)}  sig={len(sig)}", flush=True)
    src = TTFont(AF._pick_src(None))
    changed = []

    # locate the 3 News Gothic in `content` by their extracted signatures, inject in place
    import glob
    ng_files = [f for f in glob.glob(r"C:\tmp\acuwork\fonts\*News_Gothic*.ttf")]
    done = 0
    for fp in ng_files:
        d = open(fp, "rb").read()
        off = bytes(content).find(d[:40])
        if off < 0:
            print("  !! font not found:", os.path.basename(fp), flush=True)
            continue
        # embedded size = the u32 right before the sfnt (marker at off-8, size at off-4)
        esz = struct.unpack_from("<I", content, off - 4)[0]
        orig = bytes(content[off:off + esz])
        nt = heb_font(orig, src)
        if len(nt) > esz:
            print(f"  !! {os.path.basename(fp)} {len(nt)} > slot {esz}", flush=True)
            continue
        content[off:off + esz] = nt + b"\x00" * (esz - len(nt))   # pad to keep length
        changed.append((off, off + esz))
        r = TTFont(io.BytesIO(nt), lazy=True)
        h = sum(1 for c in range(0x05D0, 0x05EB) if c in r.getBestCmap())
        print(f"  injected {os.path.basename(fp)} @0x{off:x} esz={esz} new={len(nt)} heb={h}/27", flush=True)
        done += 1
    print(f"injected {done} News Gothic fonts; changed ranges: {changed}", flush=True)

    # content length unchanged -> field2 unchanged. Recompress ONLY changed blocks (keep the
    # rest byte-identical) so the result is guaranteed <= the original on-disk size.
    print("partial re-LZO (only changed blocks) ...", flush=True)
    newcfd2 = cfd_partial.rebuild_partial(compinfo7, blocks, content, changed)
    newdata = blob[:p1] + newcfd2 + sig
    print(f"new .data {len(newdata):,}  slot {slot:,}  FITS in-place: {len(newdata) <= slot}", flush=True)
    open(r"C:\tmp\acuwork\bootstrap_HE.data", "wb").write(newdata)

    # verify: re-decompress newdata, check fonts have Hebrew + content byte-identical
    q1, _ = L.cfd_decompress(newdata, 0)
    q2, c2 = L.cfd_decompress(newdata, q1)
    print("verify content len:", len(c2), "== orig", len(c2) == len(content),
          " byte-identical:", bytes(c2) == bytes(content), flush=True)
    ok = 0
    for (off, end) in changed:
        ft = TTFont(io.BytesIO(bytes(c2[off:end])), lazy=True)
        if sum(1 for c in range(0x05D0, 0x05EB) if c in ft.getBestCmap()) == 27:
            ok += 1
    print(f"verify: {ok}/{len(changed)} News Gothic have full Hebrew in rebuilt .data", flush=True)


if __name__ == "__main__":
    main()
