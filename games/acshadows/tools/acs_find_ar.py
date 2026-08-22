#!/usr/bin/env python3
"""Search a forge for pre-shaped (presentation-form) Arabic words, in BOTH
logical and visual (reversed) order, UTF-16LE. Reports resource + context."""
import sys, os, struct, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_forge as F, acs_cfd as C
import arabic_reshaper


def needles(words):
    out = []
    for w in words:
        r = arabic_reshaper.reshape(w)
        out.append((f"{w} [logical]", r.encode("utf-16-le")))
        out.append((f"{w} [visual]", r[::-1].encode("utf-16-le")))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("forge"); ap.add_argument("words", nargs="+")
    ap.add_argument("--max-size", type=int, default=20_000_000)
    a = ap.parse_args()
    o = C._oodle(); info = F.parse(a.forge); base = os.path.basename(a.forge)
    nds = needles(a.words)
    hits = 0
    for k, r in enumerate(info["recs"]):
        if k % 5000 == 0:
            print(f"  {base}: {k}/{info['count']}, {hits} hits", flush=True)
        if r["size"] > a.max_size or r["size"] < 32:
            continue
        try:
            with open(a.forge, "rb") as f:
                f.seek(r["offset"]); blob = f.read(r["size"])
            data = b"".join(d for d, _ in C.decode_resource(blob, o)[0])
        except Exception:
            continue
        for label, ub in nds:
            p = data.find(ub)
            if p >= 0:
                hits += 1
                lpre = struct.unpack_from("<I", data, p - 4)[0] if p >= 4 else -1
                print(f"  HIT idx {r['i']} size 0x{r['size']:x} flags {r['flags']} "
                      f"hash 0x{r['hash']:08x} : {label} @0x{p:x} u32_before={lpre}", flush=True)
    print(f"DONE {base}: {hits} hits", flush=True)


if __name__ == "__main__":
    main()
