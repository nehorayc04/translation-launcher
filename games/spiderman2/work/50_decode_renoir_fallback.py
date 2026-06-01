"""Decode the script-fallback config in RenoirCore — what FONT NAMES (if any)
follow 'hebrew' vs 'arabic'?"""
import os, sys, struct, re
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
d = open(os.path.join(GAME, "RenoirCore.WindowsDesktop.dll"), "rb").read()

# We saw: hebrew@1700368, arabic@1727888 - dump much more context
# 64 KB around each
WIN = 32768

for script_name in ("hebrew", "arabic", "latin", "thai", "hangul"):
    s_bytes = script_name.encode("ascii")
    j = d.find(s_bytes)
    if j < 0: continue
    print(f"\n=== {script_name}@{j} — {WIN*2} bytes around ===")
    start = max(0, j - WIN)
    end = min(len(d), j + WIN)
    chunk = d[start:end]
    # Extract ASCII strings >= 4 chars
    strings = re.findall(rb'[ -~]{4,80}', chunk)
    # Print them
    for s in strings[:60]:
        # show offset
        idx = chunk.find(s)
        abs_off = start + idx
        print(f"  [{abs_off:>8}] {s.decode('ascii','replace')!r}")
