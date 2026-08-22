#!/usr/bin/env python3
"""Find resources that densely contain real presentation-form Arabic strings
(bare [u32 len][UTF-16LE] records). Those are the per-language Arabic UI/text
resources (Arabic in AC Shadows is stored pre-shaped, U+FB50..U+FEFF)."""
import sys, os, struct, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_forge as F, acs_cfd as C


def ar_strings(data):
    """count bare strings that are >=4 contiguous Arabic presentation forms."""
    n = len(data); p = 0; cnt = 0; sample = []
    while p + 4 <= n:
        L = struct.unpack_from("<I", data, p)[0]
        if 1 <= L <= 400 and p + 4 + 2 * L <= n:
            raw = data[p + 4:p + 4 + 2 * L]
            try:
                s = raw.decode("utf-16-le")
            except Exception:
                p += 1; continue
            af = sum(1 for c in s if 'ﭐ' <= c <= '﻿' or '؀' <= c <= 'ۿ')
            if af >= 4 and af >= len(s) // 2:
                cnt += 1
                if len(sample) < 3:
                    sample.append(s[:30])
                p += 4 + 2 * L; continue
        p += 1
    return cnt, sample


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("forge"); ap.add_argument("--min", type=int, default=8)
    ap.add_argument("--max-size", type=int, default=15_000_000)
    a = ap.parse_args()
    o = C._oodle(); info = F.parse(a.forge); base = os.path.basename(a.forge)
    hits = []
    for k, r in enumerate(info["recs"]):
        if k % 5000 == 0:
            print(f"  {base}: {k}/{info['count']}, {len(hits)} AR-resources", flush=True)
        if r["size"] > a.max_size or r["size"] < 64:
            continue
        try:
            with open(a.forge, "rb") as f:
                f.seek(r["offset"]); blob = f.read(r["size"])
            data = b"".join(d for d, _ in C.decode_resource(blob, o)[0])
        except Exception:
            continue
        cnt, sample = ar_strings(data)
        if cnt >= a.min:
            hits.append((r["i"], cnt, r["size"], r["flags"], r["hash"], sample))
            print(f"  AR idx {r['i']} count {cnt} size 0x{r['size']:x} flags {r['flags']} "
                  f"hash 0x{r['hash']:08x} :: {sample}", flush=True)
    hits.sort(key=lambda h: -h[1])
    print(f"DONE {base}: {len(hits)} Arabic-string resources", flush=True)
    for i, c, sz, fl, h, sm in hits[:30]:
        print(f"  idx {i:>7} count {c:>5} hash 0x{h:08x}")


if __name__ == "__main__":
    main()
