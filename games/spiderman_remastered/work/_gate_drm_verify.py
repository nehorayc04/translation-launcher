"""Verify the install against its own vendor manifest (_Redist/fitgirl.md5).
READ-ONLY. Proves the archives/exe on disk are the ones the repack shipped,
so any later 'modified archive' test starts from a known-pristine baseline."""
import hashlib, os

GAME = r"D:\Games\Spider-man Remastered"
MAN = os.path.join(GAME, "_Redist", "fitgirl.md5")

ok = bad = miss = 0
rows = []
for line in open(MAN, encoding="utf-8", errors="replace"):
    line = line.strip()
    if not line:
        continue
    h, _, p = line.partition(" *")
    p = p.lstrip(".").lstrip("\\").lstrip("/")
    p = p.replace("/", os.sep)
    full = os.path.join(GAME, p)
    if not os.path.exists(full):
        miss += 1
        rows.append(("MISSING", p, ""))
        continue
    d = hashlib.md5()
    with open(full, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            d.update(c)
    if d.hexdigest() == h.lower():
        ok += 1
    else:
        bad += 1
        rows.append(("MISMATCH", p, d.hexdigest()))

print(f"vendor manifest: OK={ok}  MISMATCH={bad}  MISSING={miss}")
for r in rows[:25]:
    print("   ", r)
