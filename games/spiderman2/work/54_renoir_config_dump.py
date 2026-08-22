"""Dump the Renoir text-config schema + the hebrew/arabic regions, with hex,
to learn the per-script fallback structure."""
import os, re, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
d = open(os.path.join(GAME, "RenoirCore.WindowsDesktop.dll"), "rb").read()


def strings_near(off, win=1400, minlen=3):
    start = max(0, off - 200)
    end = min(len(d), off + win)
    chunk = d[start:end]
    for m in re.finditer(rb"[ -~]{%d,120}" % minlen, chunk):
        yield start + m.start(), m.group().decode("latin-1")


print("=" * 72)
print("REGION 1: 'fallback-script' / 'default-script' config schema")
print("=" * 72)
anchor = d.find(b"fallback-script")
print(f"anchor @ {anchor}")
for off, s in strings_near(anchor, win=2000, minlen=3):
    print(f"  [{off:>9}] {s!r}")

for label, tok in (("hebrew", b"hebrew"), ("arabic", b"arabic")):
    print("\n" + "=" * 72)
    print(f"REGION: {label!r} string + surrounding strings")
    print("=" * 72)
    j = d.find(tok)
    print(f"anchor @ {j}")
    # nearby readable strings within +-3KB
    for off, s in strings_near(j, win=3000, minlen=3):
        # filter to interesting ones
        print(f"  [{off:>9}] {s!r}")
