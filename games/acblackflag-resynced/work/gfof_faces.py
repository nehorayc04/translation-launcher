# -*- coding: utf-8 -*-
"""Walk ALL font faces in a GFOF resource by following the global bitmap-offset
chain across face boundaries, then pin down the bitmap blob base."""
import os, sys, struct, collections

ATLAS = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas"
REC, FMT = 36, "<7f2I"

def rd(data, o):
    return struct.unpack_from(FMT, data, o)

def sane(r, expect_bo=None):
    adv, x0, y0, x1, y1, w, h, bo, cp = r
    if not (0 <= cp <= 0x10FFFF): return False
    if w != int(w) or h != int(h): return False
    if not (0 <= w <= 1024 and 0 <= h <= 1024): return False
    if not all(-4096 < v < 4096 for v in (adv, x0, y0, x1, y1)): return False
    if expect_bo is not None and bo != expect_bo: return False
    return True

def walk(data, start):
    """Walk faces. Returns list of faces: dict(rec_start, n, hdr_start)."""
    faces = []
    o = start
    bo_expect = None
    while o + REC <= len(data):
        # walk records from o
        n = 0
        cur = o
        exp = bo_expect
        while cur + REC <= len(data):
            r = rd(data, cur)
            if not sane(r, exp): break
            exp = r[7] + int(r[5]) * int(r[6])
            n += 1
            cur += REC
        if n == 0:
            break
        faces.append(dict(rec_start=o, n=n, rec_end=cur, first_bo=rd(data, o)[7], reach=exp))
        bo_expect = exp
        # search forward for the next face's first record: chain must continue at exp
        nxt = None
        for probe in range(cur, min(cur + 512, len(data) - REC), 4):
            r = rd(data, probe)
            if sane(r, bo_expect):
                # require at least 2 chained records to avoid false hits
                r2o = probe + REC
                exp2 = r[7] + int(r[5]) * int(r[6])
                if r2o + REC <= len(data):
                    r2 = rd(data, r2o)
                    if sane(r2, exp2):
                        nxt = probe
                        break
                else:
                    nxt = probe
                    break
        if nxt is None:
            break
        o = nxt
    return faces

def main():
    sel = sys.argv[1] if len(sys.argv) > 1 else None
    for fn in sorted(f for f in os.listdir(ATLAS) if f.endswith(".bin")):
        if sel and sel not in fn: continue
        data = open(os.path.join(ATLAS, fn), "rb").read()
        g = data.find(b"GFOF")
        n0 = struct.unpack_from("<I", data, g + 0x24)[0]
        faces = walk(data, g + 0x48)
        total = sum(f["n"] for f in faces)
        reach = faces[-1]["reach"] if faces else 0
        print("=" * 96)
        print(f"{fn}  size={len(data)} (0x{len(data):x})  GFOF@0x{g:x}  hdrCount={n0}")
        print(f"  faces={len(faces)}  totalGlyphs={total}  finalReach={reach}  "
              f"size-reach={len(data)-reach}  lastRecEnd=0x{faces[-1]['rec_end']:x}" if faces else "")
        for k, f in enumerate(faces):
            hdrgap = f["rec_start"] - (faces[k-1]["rec_end"] if k else g + 0x48)
            cnt_at = struct.unpack_from("<I", data, f["rec_start"] - 0x24)[0]
            prev_at = struct.unpack_from("<I", data, f["rec_start"] - 4)[0]
            cps = [rd(data, f["rec_start"] + i * REC)[8] for i in range(f["n"])]
            b = collections.Counter()
            for c in cps:
                if c < 0x80: b["ASCII"] += 1
                elif c < 0x250: b["Lat-ext"] += 1
                elif 0x370 <= c < 0x400: b["Greek"] += 1
                elif 0x400 <= c < 0x530: b["Cyr"] += 1
                elif 0x590 <= c < 0x600: b["HEBREW"] += 1
                elif 0x600 <= c < 0x700: b["Arabic"] += 1
                elif 0xE000 <= c < 0xF900: b["PUA"] += 1
                elif 0xFB50 <= c < 0xFE00: b["ArabPresA"] += 1
                elif 0xFE70 <= c < 0xFF00: b["ArabPresB"] += 1
                elif 0x3040 <= c < 0x3100: b["Kana"] += 1
                elif 0x4E00 <= c < 0xA000: b["CJK"] += 1
                elif 0xAC00 <= c < 0xD7A4: b["Hangul"] += 1
                else: b["misc"] += 1
            print(f"   face{k:>2}: rec@0x{f['rec_start']:06x} n={f['n']:<5} gap={hdrgap:<4} "
                  f"cnt@-0x24={cnt_at:<6} @-4={prev_at:<7} bo0={f['first_bo']:<10} reach={f['reach']:<10} "
                  f"{dict(b.most_common(5))}")
        print()

if __name__ == "__main__":
    main()
