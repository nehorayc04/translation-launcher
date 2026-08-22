#!/usr/bin/env python3
"""Crash-isolated resource scanner. A single batch [lo,hi) of resource indices
is decoded in THIS process; the driver (acbf_scan_all.py) runs each batch as a
subprocess so an Oodle segfault only loses one batch. Prints JSON lines:
  {"i":idx,"hash":"0x..","tag":bool,"ar":bool,"sample":".."}
for every resource that has a FADE9F44 record OR a real Arabic run."""
import importlib.util, os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "acshadows", "tools"))
os.environ.setdefault("ACS_OODLE_DLL", r"C:\Games\Battlefield 6\oo2core_9_win64.dll")
from acs_oodle import Oodle

def _load(n):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), n + ".py")
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
L = _load("acbf_loc"); AF = _load("acbf_forge")


def real_arabic_run(d, run=6):
    n = len(d) - 1; i = 0
    while i < n - run * 2:
        if d[i + 1] == 0x06 and 0x21 <= d[i] <= 0x4a:
            k = 0
            while i + k * 2 + 1 < n:
                lo, hi = d[i + k * 2], d[i + k * 2 + 1]
                if hi == 0x06 and lo <= 0x52: k += 1
                elif hi == 0x00 and lo == 0x20: k += 1
                else: break
            if k >= run: return i
            i += (k + 1) * 2
        else: i += 1
    return -1


def main():
    fn, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    o = Oodle()
    info = AF.parse(fn); recs = info["recs"]
    f = open(fn, "rb")
    for r in recs[lo:hi]:
        if r["size"] < 40 or r["size"] > 8_000_000:
            continue
        f.seek(r["offset"]); blob = f.read(r["size"])
        if blob[:4] != b"\x33\xaa\xfb\x57":
            continue
        try:
            dec = L.decode_blob(blob, o)
        except Exception:
            continue
        if not dec:
            continue
        tag = L.TAG in dec
        arp = real_arabic_run(dec)
        if tag or arp >= 0:
            samp = ""
            if tag:
                for _, _, txt in L.records_in(dec):
                    samp = txt[:40]; break
            elif arp >= 0:
                samp = dec[arp:arp + 40].decode("utf-16-le", "replace")
            print(json.dumps({"i": r["i"], "hash": f"0x{r['hash']:08x}",
                              "size": r["size"], "tag": tag, "ar": arp >= 0,
                              "sample": samp}, ensure_ascii=False), flush=True)
    f.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
