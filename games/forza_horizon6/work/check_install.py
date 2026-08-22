"""Verify the FH6 install against the game's own xxh128 manifest (existence + size).

Hashing 144 GB is pointless here — a MISSING file is the question, and the
manifest lists every file the build is supposed to ship.
"""
import os, sys, glob

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
GAME = r"C:\Games\Forza Horizon 6"

man = sorted(glob.glob(os.path.join(GAME, "*.xxh128")))
if not man:
    sys.exit("no .xxh128 manifest found")
print("manifest:", os.path.basename(man[-1]))

missing, present, empty = [], 0, []
for line in open(man[-1], "r", encoding="utf-8", errors="replace"):
    line = line.rstrip("\n")
    if " *" not in line:
        continue
    _h, rel = line.split(" *", 1)
    full = os.path.join(GAME, rel.replace("/", os.sep))
    if not os.path.exists(full):
        missing.append(rel)
    else:
        present += 1
        if os.path.getsize(full) == 0:
            empty.append(rel)

print(f"listed {present + len(missing)}   present {present}   MISSING {len(missing)}   zero-byte {len(empty)}")
if missing:
    print("\n--- missing ---")
    for m in missing[:60]:
        print("  ", m)
    if len(missing) > 60:
        print(f"   ... +{len(missing) - 60} more")
if empty:
    print("\n--- zero-byte ---")
    for m in empty[:20]:
        print("  ", m)
