#!/usr/bin/env python3
"""Crash-isolated batch: decode resources [lo,hi) in a v50 forge and report any
that contain a LocalizationPackage — detected by the char-index MARKER
0xD28389B5 and/or the ATK class hash 0x6E37B1AF in the DECODED bytes. Prints
JSON lines {i,hash,size,marker,classhash,nmark}. The main (multi-language incl.
Arabic) loc is char-index encoded (AC2-style), so a raw UTF-16 search misses it;
this looks for the container markers instead."""
import importlib.util, os, sys, json, struct
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "acshadows", "tools"))
os.environ.setdefault("ACS_OODLE_DLL", r"C:\Games\Battlefield 6\oo2core_9_win64.dll")
from acs_oodle import Oodle

def _load(n):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), n + ".py")
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
L = _load("acbf_loc"); AF = _load("acbf_forge")

MARKER = struct.pack("<I", 0xD28389B5)
CLASSH = struct.pack("<I", 0x6E37B1AF)


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
        nm = dec.count(MARKER)
        ch = dec.count(CLASSH)
        if nm or ch:
            print(json.dumps({"i": r["i"], "hash": f"0x{r['hash']:08x}",
                              "size": r["size"], "declen": len(dec),
                              "marker": nm, "classhash": ch}), flush=True)
    f.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
