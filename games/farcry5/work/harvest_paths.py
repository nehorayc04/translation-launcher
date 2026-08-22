"""Harvest the REAL virtual file paths out of FC5's Scaleform SWFs.

FC5's UI ("ZETA") SWFs carry proprietary tags that embed plain-text asset paths:
    tag 243 / 246 -> external image   (u16 id, u16 w, u16 h, path)
    tag 244       -> "SuperTexture"   (.bfd atlas descriptor paths)
    tag 71        -> ImportAssets2    (.feu = FC5's SWF extension)
Since we also have the exact name hash (CRC64, lowercase, backslash), any harvested path
can be turned straight back into an archive entry.  This is the filelist the game never ships.

  python harvest_paths.py [archive.fat ...]     -> extract/paths.txt
"""
import sys, os, re, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fc5_fat import Fat
from fc5_crc64 import name_hash
import find_swf_fonts as F

PC = os.path.join(os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5"),
                  "data_final", "pc")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "extract")
os.makedirs(OUT, exist_ok=True)

PATH_RX = re.compile(rb"[\x20-\x7e]{6,180}")
archives = sys.argv[1:] or ["common.fat", "patch.fat", "worlds/installpkg.fat"]

paths = set()
for arch in archives:
    p = os.path.join(PC, arch)
    if not os.path.exists(p):
        continue
    f = Fat(p)
    n = 0
    for e in f.entries:
        if not (64 <= e.unc <= 40_000_000):
            continue
        try:
            b = f.read_data(e)
        except Exception:
            continue
        if b[:3] not in (b"UEF", b"CEF"):
            continue
        n += 1
        for code, d in F.tags(F.deobfuscate(b)):
            if code not in (243, 244, 246, 71, 56):
                continue
            for m in PATH_RX.finditer(d):
                s = m.group().decode("latin-1")
                for part in s.split("\x00"):
                    part = part.strip()
                    if ("\\" in part or "/" in part) and "." in part and len(part) > 8:
                        paths.add(part)
    print(f"{arch}: {n} SWFs, running total {len(paths):,} paths", flush=True)

paths = sorted(paths)
with open(os.path.join(OUT, "paths.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(paths))
print(f"\nharvested {len(paths):,} unique paths -> extract/paths.txt")

ext = collections.Counter(os.path.splitext(p)[1].lower() for p in paths)
print("extensions:", dict(ext.most_common(12)))

top = collections.Counter(p.replace("/", "\\").split("\\")[0].lower() for p in paths)
print("top-level dirs:", dict(top.most_common(10)))

print("\n=== FONT-ish paths ===")
fonts = [p for p in paths if re.search(r"(?i)font|glyph|charset|typeface|text_?set", p)]
for p in fonts[:60]:
    h = name_hash(p.replace("/", "\\"))
    print(f"  {p}")
print(f"({len(fonts)} font-ish paths)")

# resolve every harvested path against every archive
import glob
fats = {}
for q in sorted(glob.glob(PC + "/**/*.fat", recursive=True)):
    if os.path.getsize(q) < 64:
        continue
    try:
        ff = Fat(q)
        if ff.count:
            fats[os.path.relpath(q, PC)] = ff
    except Exception:
        pass
hit = 0
print("\n=== resolving font-ish paths to archive entries ===")
for p in fonts:
    h = name_hash(p)
    for k, ff in fats.items():
        e = ff.by_hash.get(h)
        if e:
            print(f"  HIT {p}  -> {k} sch={e.scheme} unc={e.unc:,}")
            hit += 1
print(f"resolved {hit}")

# how many of ALL harvested paths resolve? (tells us the hash+convention is right)
res = sum(1 for p in paths[:400] if any(name_hash(p) in ff.by_hash for ff in fats.values()))
print(f"\nsanity: {res}/400 sampled paths resolve to a real entry")
