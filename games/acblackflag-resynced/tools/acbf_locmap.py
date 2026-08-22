#!/usr/bin/env python3
"""Definitive loc map: scan small resources (<=512KB) with the FIXED multi-block
CFD decoder and, per nameHash, count FADE9F44 records, WORD-LIKE Arabic runs
(non-monotonic real letters, not a numeric dict), and char-index markers.
Writes /tmp/acbf_locmap.txt."""
import importlib.util, os, sys, struct, time
from collections import defaultdict


def _load(n):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), n + ".py")
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
CFD = _load("acbf_cfd"); L = _load("acbf_loc"); AF = _load("acbf_forge")

FADE = struct.pack("<I", 0xFADE9F44)
MK1 = struct.pack("<I", 0xD28389B5)
MK2 = struct.pack("<I", 0x6E37B1AF)


def wordish_arabic(d):
    """A run of >=8 Arabic LETTERS that is NOT strictly monotonic (real words,
    not a sorted char dictionary or numeric u16 data)."""
    n = len(d) - 1; i = 0
    while i < n - 16:
        if d[i + 1] == 0x06 and 0x27 <= d[i] <= 0x4a:
            j = i; letters = 0; last = -1; mono = True
            while j < n:
                lo, hi = d[j], d[j + 1]
                if hi == 0x06 and 0x21 <= lo <= 0x4a:
                    letters += 1
                    if lo <= last:
                        mono = False
                    last = lo; j += 2
                elif hi == 0x00 and lo == 0x20:
                    j += 2; last = -1
                elif hi == 0x06 and lo <= 0x52:
                    j += 2
                else:
                    break
            if letters >= 8 and not mono:
                return i
            i = max(j, i + 2)
        else:
            i += 2
    return -1


def main():
    fn = sys.argv[1]
    o = CFD._oodle()
    info = AF.parse(fn); recs = info["recs"]
    byhash = defaultdict(lambda: {"tag": 0, "ar": 0, "mk": 0, "n": 0, "samp": ""})
    probed = 0; f = open(fn, "rb"); t0 = time.time()
    out = open("/tmp/acbf_locmap.txt", "w", encoding="utf-8")
    for r in recs:
        if r["size"] < 40 or r["size"] > 524288:
            continue
        probed += 1
        if probed % 20000 == 0:
            print(f"  probed {probed} ({time.time()-t0:.0f}s)", flush=True)
        f.seek(r["offset"]); blob = f.read(r["size"])
        if len(blob) < 8 or struct.unpack_from("<Q", blob, 0)[0] != CFD.MAGIC:
            continue
        try:
            dec = L.decode_blob(blob, o)
        except Exception:
            continue
        if not dec:
            continue
        h = f"0x{r['hash']:08x}"; d = byhash[h]; hit = False
        if FADE in dec:
            d["tag"] += 1; hit = True
        ap = wordish_arabic(dec)
        if ap >= 0:
            d["ar"] += 1; hit = True
            if not d["samp"]:
                d["samp"] = dec[ap:ap + 40].decode("utf-16-le", "replace")
        if MK1 in dec or MK2 in dec:
            d["mk"] += 1; hit = True
        if hit:
            d["n"] += 1
    f.close()
    rows = sorted(byhash.items(), key=lambda kv: -kv[1]["n"])
    lines = [f"probed {probed} resources <=512KB in {time.time()-t0:.0f}s",
             "hash : n : FADE : wordArabic : markers : sample"]
    for h, d in rows[:40]:
        if d["n"]:
            lines.append(f"  {h} : n={d['n']:>5} tag={d['tag']:>5} ar={d['ar']:>4} mk={d['mk']:>3}  {d['samp']!r}")
    txt = "\n".join(lines)
    print("\n" + txt)
    out.write(txt); out.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
