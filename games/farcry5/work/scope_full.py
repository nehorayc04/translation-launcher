"""FC5 FULL scope: UI oasis + SUBTITLES oasis, across common.fat and patch.fat.

patch overrides common, so the EFFECTIVE corpus = common merged with patch (patch wins).
Reports the three honest numbers: records - per-file uniques - GLOBAL uniques.
"""
import sys, os, re, json, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from fc5_fat import Fat
from fc5_crc64 import name_hash
import fc5_oasis as O

G = os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5")
PC = os.path.join(G, "data_final", "pc")
OASES = {"ui": "languages/{lang}/oasisstrings.oasis.bin",
         "subs": "languages/{lang}/oasisstrings_subtitles.oasis.bin"}
ARCH = ["common.fat", "patch.fat"]


def load(arch, lang, kind):
    f = Fat(os.path.join(PC, arch))
    e = f.by_hash.get(name_hash(OASES[kind].format(lang=lang)))
    if not e:
        return None
    ver, secs = O.parse(f.read_data(e))
    return O.flat(secs)


def effective(lang, kind):
    """common merged with patch (patch wins) = what the engine actually resolves."""
    base = load("common.fat", lang, kind) or {}
    over = load("patch.fat", lang, kind) or {}
    m = dict(base); m.update(over)
    return m, base, over


print("=" * 84)
print("FAR CRY 5 — FULL CORPUS SCOPE")
print("=" * 84)

corpus = {}
for kind in ("ui", "subs"):
    m, base, over = effective("english", kind)
    corpus[kind] = m
    print(f"\n[{kind}]  common={len(base):,}  patch={len(over):,}  "
          f"EFFECTIVE(union, patch wins)={len(m):,}   patch-only={len(set(over)-set(base)):,}  "
          f"common-only={len(set(base)-set(over)):,}")

ui, subs = corpus["ui"], corpus["subs"]
overlap = set(ui) & set(subs)
allk = set(ui) | set(subs)
print(f"\nkey overlap between the two oases: {len(overlap):,}")
print(f"TOTAL distinct (sectionCRC,id) keys : {len(allk):,}")

merged = dict(ui); merged.update(subs)
vals = list(merged.values())
uniq_text = set(vals)
chars = sum(len(v) for v in vals)
print(f"TOTAL records                       : {len(vals):,}")
print(f"TOTAL unique English strings        : {len(uniq_text):,}")
print(f"TOTAL characters                    : {chars:,}")

for tag, d in (("UI", ui), ("SUBTITLES", subs)):
    L = sorted(len(v) for v in d.values()); n = len(L)
    b = collections.Counter()
    for x in L:
        b["empty" if x == 0 else "<=25" if x <= 25 else "26-140" if x <= 140 else ">140"] += 1
    print(f"\n{tag:9s} n={n:,} chars={sum(L):,} median={L[n//2]} p90={L[int(n*.9)]} max={max(L):,}")
    print(f"          bands={dict(b)}")

print("\nsubtitle samples:")
for k, v in list(subs.items())[:3]:
    print(f"   {v[:120]!r}")
for k, v in sorted(subs.items(), key=lambda kv: -len(kv[1]))[:2]:
    print(f"   [{len(v)}] {v[:120]!r}")

# --- token inventory over the merged corpus ---
PATS = {"{tag}": r"\{[^}]{0,60}\}", "<tag>": r"<[^>]{0,60}>", "[TOKEN]": r"\[[^\]]{0,60}\]",
        "%spec": r"%[-+ #0-9.]*[a-zA-Z]", "\\n": r"\n", "&ent;": r"&[a-zA-Z#0-9]{1,10};"}
print("\ntoken inventory (merged corpus):")
for name, p in PATS.items():
    rx = re.compile(p); occ = collections.Counter()
    for v in vals:
        for m in rx.findall(v):
            occ[m] += 1
    print(f"  {name:8s} occ={sum(occ.values()):>6} distinct={len(occ):>5} top={[k for k,_ in occ.most_common(5)]}")

# --- how many oracle languages line up on the same keys? ---
print("\noracle-language key parity (subtitles oasis):")
for lang in O.LANGS:
    m, _, _ = effective(lang, "subs")
    if not m:
        print(f"  {lang:10s} absent"); continue
    same = len(set(m) & set(subs))
    print(f"  {lang:10s} strings={len(m):>7,}  shares {same:>7,} keys with english "
          f"({same/len(subs)*100:.1f}%)")

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "extract")
os.makedirs(out, exist_ok=True)
json.dump({f"{a:08x}:{b}": v for (a, b), v in merged.items()},
          open(os.path.join(out, "en_corpus.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print(f"\nwrote extract/en_corpus.json  ({len(merged):,} entries)")
