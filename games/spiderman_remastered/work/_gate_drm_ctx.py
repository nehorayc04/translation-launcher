"""Dump the surrounding printable string for each integrity-ish hit, so a COUNT
can be judged as benign-vs-gate. READ-ONLY."""
import re, sys

NEEDLES = ["SHA256", "integrity", "Integrity", "WinVerifyTrust", "tamper",
           "Signature", "SIGNATURE", "signature"]
PRINT = re.compile(rb"[\x20-\x7e]{4,}")


def surrounding(data, pos, span=160):
    lo = max(0, pos - span)
    hi = min(len(data), pos + span)
    best = None
    for m in PRINT.finditer(data, lo, hi):
        if m.start() <= pos < m.end():
            best = m.group().decode("latin1")
            break
    if best is None:
        chunk = data[max(0, pos - 40):pos + 60]
        best = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
    return best


def main(path, cap=25):
    data = open(path, "rb").read()
    for n in NEEDLES:
        hits = [m.start() for m in re.finditer(re.escape(n.encode()), data)]
        print(f"\n### {n}  -> {len(hits)} hit(s)")
        seen = set()
        shown = 0
        for p in hits:
            s = surrounding(data, p)
            if s in seen:
                continue
            seen.add(s)
            print(f"   @0x{p:08X}  {s[:190]}")
            shown += 1
            if shown >= cap:
                print(f"   ... ({len(hits) - shown} more)")
                break


if __name__ == "__main__":
    main(sys.argv[1])
