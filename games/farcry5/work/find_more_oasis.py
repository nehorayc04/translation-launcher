"""Hunt for additional OASIS text blobs (subtitles) across every FC5 archive.

Two passes:
  1) name-hash probe over a broad candidate path set
  2) CONTENT scan: any entry whose payload parses as an oasis (version=1 + sane sections)
     -- cheap for scheme-0 (read 8 bytes), full decompress only for plausible LZ4 sizes.
"""
import sys, os, glob, struct, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from fc5_fat import Fat
from fc5_crc64 import name_hash
import fc5_oasis as O

G = os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5")
PC = os.path.join(G, "data_final", "pc")

fats = {}
for p in sorted(glob.glob(PC + r"/**/*.fat", recursive=True)):
    if os.path.getsize(p) < 64:
        continue
    try:
        f = Fat(p)
        if f.count:
            fats[os.path.relpath(p, PC)] = f
    except Exception as ex:
        print("skip", p, ex)
print(f"archives: {len(fats)}  total entries: {sum(f.count for f in fats.values()):,}\n")

# ---------- pass 1: name probe ----------
LANGS = O.LANGS + ["default"]
SUF = ["", "_subtitles", "_subtitle", "_dialogue", "_dialog", "_conversations",
       "_soundbinary", "_vo", "_cinematic", "_worlds", "_world", "_2", "_extra"]
PRE = ["languages", "languages/worlds", "worlds/languages", "soundbinary/languages"]
cands = set()
for pre in PRE:
    for lang in LANGS:
        for suf in SUF:
            cands.add(f"{pre}/{lang}/oasisstrings{suf}.oasis.bin")
            cands.add(f"{pre}/{lang}/oasisstrings{suf}.bin")
for w in ["fc5_main", "farcry5", "main", "world"]:
    for lang in LANGS:
        cands.add(f"worlds/{w}/languages/{lang}/oasisstrings.oasis.bin")
        cands.add(f"{w}/languages/{lang}/oasisstrings.oasis.bin")

print("--- pass 1: name-hash probe ---")
seen = set()
for c in sorted(cands):
    h = name_hash(c)
    for k, f in fats.items():
        if h in f.by_hash:
            e = f.by_hash[h]
            print(f"  HIT {c}  -> {k}  sch={e.scheme} unc={e.unc:,}")
            seen.add(h)
print(f"  named hits: {len(seen)}\n")

# ---------- pass 2: content scan ----------
print("--- pass 2: content scan for oasis signature ---")
found = []
for k, f in fats.items():
    hits = 0
    dat = f.dat_path
    if not os.path.exists(dat):
        continue
    fh = open(dat, "rb")
    for e in f.entries:
        if e.unc < 2048 or e.unc > 40_000_000:
            continue
        try:
            if e.scheme == 0:
                fh.seek(e.off); head = fh.read(8)
            else:
                head = f.read_data(e)[:8]
        except Exception:
            continue
        if len(head) < 8:
            continue
        ver, sc = struct.unpack("<II", head)
        if ver == 1 and 1 <= sc <= 20000:
            # confirm it really parses
            try:
                v, secs = O.parse(f.read_data(e))
            except Exception:
                continue
            vals = O.flat(secs)
            if len(vals) < 5:
                continue
            found.append((k, e.hash, len(secs), len(vals), e.unc))
            hits += 1
    fh.close()
    if hits:
        print(f"  {k}: {hits} oasis blob(s)")

print("\n--- all oasis blobs found ---")
tot = collections.Counter()
for k, h, ns, nv, unc in sorted(found, key=lambda t: -t[3]):
    print(f"  {k:42s} {h:016x} sections={ns:>5} strings={nv:>7,} unc={unc:>10,}")
    tot[k] += nv
print("\nper-archive string totals:", dict(tot))
