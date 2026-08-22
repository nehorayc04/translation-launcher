#!/usr/bin/env python3
"""Dump every GFOF header word and hunt for the field that addresses the tail (region D)."""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acbf_phxfd import load, parse, FILES


def main():
    for n in FILES:
        d = load(n); hdr, recs = parse(d)
        g = hdr["gfof"]
        srt = sorted(recs, key=lambda r: r["tex"])
        first = srt[0]["tex"]
        last = max(r["tex"] + int(round(r["w"]))*int(round(r["h"])) for r in recs)
        rec_end = hdr["rec_end"]
        marks = {"recEnd": rec_end, "firstTex": first, "lastTexEnd": last,
                 "fileLen": len(d), "tailLen": len(d)-last, "gapLen": first-rec_end,
                 "count": hdr["count"], "objSize": struct.unpack_from("<I", d, 0x18)[0]}
        print(f"\n=== {n} ===   " + "  ".join(f"{k}=0x{v:x}({v})" for k, v in marks.items()))
        print(f"  GFOF@0x{g:x} header words +0..+72:")
        for o in range(0, 72, 4):
            v = struct.unpack_from("<I", d, g+o)[0]
            f = struct.unpack_from("<f", d, g+o)[0]
            tag = ""
            for k, mv in marks.items():
                if v == mv: tag += f"  <== {k}"
                if v == mv - g: tag += f"  <== {k}-GFOF"
            print(f"    +{o:2d}: u32={v:<12d} 0x{v:08x}  f32={f:<14.5f}{tag}")
        # global hunt: which u32 anywhere in the first 0x400 bytes equals a mark?
        hits = []
        for o in range(0, min(len(d)-4, 0x400)):
            v = struct.unpack_from("<I", d, o)[0]
            for k, mv in marks.items():
                if mv > 1000 and v == mv:
                    hits.append((o, k, v))
        print(f"  u32 in first 0x400 matching a landmark: {[(hex(o),k) for o,k,_ in hits]}")
        # hunt in the WHOLE file for lastTexEnd / tailLen
        for k in ("lastTexEnd", "tailLen"):
            mv = marks[k]
            pat = struct.pack("<I", mv)
            occ, i = [], -1
            while len(occ) < 6:
                i = d.find(pat, i+1)
                if i < 0: break
                occ.append(i)
            print(f"  whole-file u32 == {k}(0x{mv:x}): {[hex(x) for x in occ]}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
