"""FC5 scope report: string counts, char counts, token inventory, script check, length bands."""
import sys, os, re, collections, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from fc5_fat import Fat
from fc5_crc64 import name_hash
import fc5_oasis as O

G = os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5")
PC = os.path.join(G, "data_final", "pc")


def load(arch, lang):
    f = Fat(os.path.join(PC, arch))
    e = f.by_hash.get(name_hash(O.oasis_path(lang)))
    if not e:
        return None
    ver, secs = O.parse(f.read_data(e))
    return O.flat(secs)


def script_counts(s):
    c = collections.Counter()
    for ch in s:
        if not ch.isalpha():
            continue
        o = ord(ch)
        if o < 0x250: c["latin"] += 1
        elif 0x400 <= o < 0x530: c["cyrillic"] += 1
        elif 0x590 <= o < 0x600: c["hebrew"] += 1
        elif 0x600 <= o < 0x700: c["arabic"] += 1
        elif 0xFB50 <= o < 0xFE00 or 0xFE70 <= o < 0xFF00: c["arabic-presform"] += 1
        elif o >= 0x3000: c["cjk"] += 1
        else: c["other"] += 1
    return c


print("=" * 78)
print("FAR CRY 5 — OASIS SCOPE REPORT")
print("=" * 78)

for arch in ("common.fat", "patch.fat"):
    en = load(arch, "english")
    print(f"\n{arch}: english strings = {len(en):,}")

en = load("patch.fat", "english")          # patch overrides common -> the live copy
ar = load("patch.fat", "arabic")
enc = load("common.fat", "english")

print(f"\ncommon vs patch english identical: {en == enc}")
diff = sum(1 for k in en if enc.get(k) != en[k])
print(f"keys differing between common and patch: {diff} (of {len(en):,})")
print(f"key sets equal: {set(en) == set(enc)}")

# ---- char + length ----
chars = sum(len(v) for v in en.values())
lens = sorted(len(v) for v in en.values())
n = len(lens)
band = collections.Counter()
for L in lens:
    band["empty" if L == 0 else "<=25" if L <= 25 else "26-140" if L <= 140 else ">140"] += 1
print(f"\nstrings={n:,}  chars={chars:,}  median={lens[n//2]}  p90={lens[int(n*.9)]}  max={max(lens):,}")
print("length bands:", dict(band))

# ---- scripts ----
for tag, d in (("english", en), ("arabic", ar)):
    c = collections.Counter()
    for v in d.values():
        c += script_counts(v)
    print(f"{tag:8s} scripts: {dict(c.most_common(5))}")

# ---- tokens ----
PATS = {
    "{tag}":        re.compile(r"\{[^}]{0,60}\}"),
    "<tag>":        re.compile(r"<[^>]{0,60}>"),
    "[TOKEN]":      re.compile(r"\[[^\]]{0,60}\]"),
    "%spec":        re.compile(r"%[-+ #0-9.]*[a-zA-Z]"),
    "newline \\n":  re.compile(r"\n"),
    "&entity;":     re.compile(r"&[a-zA-Z#0-9]{1,10};"),
}
print("\ntoken inventory (english):")
for name, rx in PATS.items():
    occ = collections.Counter()
    for v in en.values():
        for m in rx.findall(v):
            occ[m] += 1
    tot = sum(occ.values())
    print(f"  {name:12s} occurrences={tot:>6}  distinct={len(occ):>4}  top={[k for k,_ in occ.most_common(6)]}")

# ---- section sizes (proxy for UI vs content) ----
f = Fat(os.path.join(PC, "patch.fat"))
ver, secs = O.parse(f.read_data(f.by_hash[name_hash(O.oasis_path("english"))]))
big = sorted(secs, key=lambda s: -len(s.values))[:12]
print(f"\nsections={len(secs)}; largest by string count:")
for s in big:
    sample = next((v for v in s.values.values() if 5 < len(v) < 45), "")
    print(f"  crc={s.nameCRC:08x} n={len(s.values):>5}  e.g. {sample!r}")

# ---- longest strings = subtitles/lore? ----
print("\nlongest english strings:")
for k, v in sorted(en.items(), key=lambda kv: -len(kv[1]))[:5]:
    print(f"  [{len(v):>5}] {v[:110]!r}")

os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "extract"), exist_ok=True)
