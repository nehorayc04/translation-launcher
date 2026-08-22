"""XXH128-verify selected FH6 files against the game's own manifest."""
import os, sys, glob, xxhash

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
GAME = r"C:\Games\Forza Horizon 6"

man = sorted(glob.glob(os.path.join(GAME, "*.xxh128")))[-1]
want = {}
for line in open(man, encoding="utf-8", errors="replace"):
    if " *" not in line:
        continue
    h, rel = line.rstrip("\n").split(" *", 1)
    want[rel.lower().replace("/", os.sep)] = h

TARGETS = sys.argv[1:] or [
    r"media\UI\Fonts.zip",
    r"media\UI.zip",
    r"media\Stripped\StringTables\EN.zip",
    r"media\Stripped\StringTables\GB.zip",
    r"media\Stripped\StringTables\RU.zip",
    r"media\zipmanifest.xml",
    r"MicrosoftGame.config",
]

for t in TARGETS:
    t = t.replace("/", os.sep)
    p = os.path.join(GAME, t)
    exp = want.get(t.lower())
    if not os.path.exists(p):
        print(f"{t:48s} FILE MISSING")
        continue
    if exp is None:
        print(f"{t:48s} not in manifest")
        continue
    h = xxhash.xxh128()
    with open(p, "rb") as f:
        while (b := f.read(1 << 20)):
            h.update(b)
    got = h.hexdigest()
    print(f"{t:48s} {'MATCH   ' if got == exp else 'MISMATCH'} exp={exp} got={got}")
