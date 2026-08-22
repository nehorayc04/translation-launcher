#!/usr/bin/env python3
"""
acs_find.py — locate a UTF-16LE needle (e.g. an Arabic UI string) inside a
forge: decompress every resource and report which ones contain it, with the
record context (bare [len][utf16] vs a 0xFADE9F44 oasis record).

    python acs_find.py "<forge>" "<needle>" [<needle2> ...] [--max-size B]
"""
import sys
import os
import struct
import argparse

TAG = struct.pack("<I", 0xFADE9F44)


def _tools():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import acs_forge as F
    import acs_cfd as C
    return F, C


def _ctx(data, p, nlen):
    pre = data[max(0, p - 24):p]
    has_tag = TAG in data[max(0, p - 40):p]
    # bare-record length prefix (u32 just before the utf16)
    lpre = struct.unpack_from("<I", data, p - 4)[0] if p >= 4 else -1
    return (f"tag_near={'Y' if has_tag else 'N'} u32_before={lpre} (chars={nlen}) "
            f"pre=" + " ".join(f"{b:02x}" for b in pre))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("forge")
    ap.add_argument("needles", nargs="+")
    ap.add_argument("--max-size", type=int, default=20_000_000)
    a = ap.parse_args()
    F, C = _tools()
    o = C._oodle()
    info = F.parse(a.forge)
    needles = [(n, n.encode("utf-16-le")) for n in a.needles]
    base = os.path.basename(a.forge)
    hits = 0
    for k, r in enumerate(info["recs"]):
        if k % 5000 == 0:
            print(f"  {base}: {k}/{info['count']} probed, {hits} hits", flush=True)
        if r["size"] > a.max_size or r["size"] < 32:
            continue
        try:
            with open(a.forge, "rb") as f:
                f.seek(r["offset"]); blob = f.read(r["size"])
            data = b"".join(d for d, _ in C.decode_resource(blob, o)[0])
        except Exception:
            continue
        for txt, ub in needles:
            p = data.find(ub)
            if p >= 0:
                hits += 1
                print(f"  HIT idx {r['i']} size 0x{r['size']:x} flags {r['flags']} "
                      f"hash 0x{r['hash']:08x} : '{txt}' @0x{p:x} | {_ctx(data, p, len(txt))}",
                      flush=True)
    print(f"DONE {base}: {hits} hits", flush=True)


if __name__ == "__main__":
    main()
