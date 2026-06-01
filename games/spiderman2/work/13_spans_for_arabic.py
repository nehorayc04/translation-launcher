"""Dump TOC2 spans and find which one(s) point at the Arabic localization entry
(index=1276510 in archive #170)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
spans = toc.get_spans_section()
print("[*] spans attrs:", [a for a in dir(spans) if not a.startswith("_")])
print("[*] spans.entries type:", type(spans.entries).__name__,
      " len:", len(spans.entries) if hasattr(spans.entries, '__len__') else '?')

# Show structure of one span entry
e0 = spans.entries[0]
print("[*] one span:", vars(e0) if hasattr(e0, '__dict__') else e0)

# Iterate spans and look for ones referencing the Arabic entry
ARABIC_INDEX = 1276510
ASSET_ID = 13715107173940066526

print()
print(f"=== spans whose range includes asset index {ARABIC_INDEX} ===")
matches = []
for i, sp in enumerate(spans.entries):
    fields = vars(sp) if hasattr(sp, '__dict__') else None
    if not fields:
        continue
    # Try to detect range membership — common attrs: start, count, base, length
    start = fields.get("first", fields.get("start", fields.get("base", -1)))
    count = fields.get("count", fields.get("length", -1))
    if start >= 0 and count >= 0:
        if start <= ARABIC_INDEX < start + count:
            print(f"  [{i}] span={fields} -> position={ARABIC_INDEX - start}")
            matches.append((i, fields, ARABIC_INDEX - start))

print(f"\n[*] total matches: {len(matches)}")

# Also: print first 5 spans + last 5 to see structure
print()
print("=== first 5 spans ===")
for i, sp in enumerate(spans.entries[:5]):
    print(f"  [{i}] {vars(sp) if hasattr(sp,'__dict__') else sp}")
print()
print("=== look at spans near the Arabic-entry index ===")
for i, sp in enumerate(spans.entries):
    fields = vars(sp) if hasattr(sp,'__dict__') else {}
    start = fields.get("first", fields.get("start", fields.get("base", -1)))
    if start < 0: continue
    if abs(start - ARABIC_INDEX) < 100:
        print(f"  [{i}] {fields}")
