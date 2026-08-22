"""MSMR — identify the near-English slot (span 152) and settle the pt/es variants
by DIFFING variants entry-by-entry against English. Read-only.

Also prints the span -> slot table (slot = span/8) so the language ENUM order is
visible, and enumerates which slots are EMPTY (no localization asset).
"""
import os, sys, json, struct
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LOCS = os.path.join(ROOT, "games", "spiderman_remastered", "extract", "loc_variants")
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import msmr_loc

fns = sorted(f for f in os.listdir(LOCS) if f.endswith(".localization"))
locs = {k: msmr_loc.Loc(os.path.join(LOCS, f)) for k, f in enumerate(fns)}
meta = {r["k"]: r for r in json.load(open(os.path.join(LOCS, "_langmap.json"),
                                          encoding="utf-8"))["variants"]}
N = locs[0].n
pairs = {k: l.pairs() for k, l in locs.items()}
keys = [k for k, _ in pairs[0]]


def diff(a, b, limit=25):
    out = []
    for i in range(N):
        if pairs[a][i][1] != pairs[b][i][1]:
            out.append((keys[i], pairs[a][i][1], pairs[b][i][1]))
    return out


print("=" * 78)
print("SPAN -> SLOT table (slot = span / 8)")
print("=" * 78)
have = {}
for k, m in meta.items():
    have[m["span"] // 8] = (k, m["lang"], m["span"])
for slot in range(0, 28):
    if slot in have:
        k, lang, span = have[slot]
        print(f"  slot {slot:2}  span {span:3}  variant_{k:02d}  {lang}")
    else:
        print(f"  slot {slot:2}  span {slot*8:3}  --- EMPTY (no localization asset) ---")

print("\n" + "=" * 78)
print("A) variant_00 vs variant_01  (both classified ENGLISH)")
print("=" * 78)
d = diff(0, 1)
print(f"  differing entries: {len(d)} / {N}")
if d:
    for k_, a, b in d[:15]:
        print(f"    {k_:40} EN0={a[:45]!r}  EN1={b[:45]!r}")
else:
    print("  => the two English slots are IDENTICAL (duplicate English)")

print("\n" + "=" * 78)
print("B) variant_17 (span 152, 86.8% == English) vs variant_00 — WHAT differs?")
print("=" * 78)
d = diff(17, 0)
print(f"  differing entries: {len(d)} / {N}  ({100*len(d)/N:.1f}%)")
pref = Counter(k_.split("_")[0] for k_, _, _ in d)
print(f"  top key prefixes among the diffs: {pref.most_common(15)}")
print("\n  25 sample diffs (variant_17  vs  ENGLISH):")
for k_, a, b in d[:25]:
    print(f"    {k_[:38]:38}\n        v17 = {a[:80]!r}\n        EN  = {b[:80]!r}")

# is v17 just English with a different dialect? measure how many diffs are
# small spelling variations vs completely different text
import difflib
close = sum(1 for k_, a, b in d[:4000]
            if a and b and difflib.SequenceMatcher(None, a, b).ratio() > 0.75)
print(f"\n  of the first {min(4000,len(d))} diffs, {close} are >75% similar to the English"
      f"  ({100*close/max(1,min(4000,len(d))):.0f}%)  -> "
      + ("dialect/spelling variant of English" if close > 0.5 * min(4000, len(d))
         else "genuinely different text"))

print("\n" + "=" * 78)
print("C) PORTUGUESE variants: variant_12 (span 104) vs variant_16 (span 144)")
print("=" * 78)
for k in (12, 16):
    txt = " ".join(v for _, v in pairs[k][:20000]).lower()
    pt = sum(txt.count(t) for t in (" tu ", " tens ", " estás ", " podes ", " ecrã ", " telemóvel ", " percebes "))
    br = sum(txt.count(t) for t in (" você ", " tem ", " está ", " pode ", " tela ", " celular ", " cara "))
    print(f"  variant_{k:02d} span={meta[k]['span']}   pt-PT markers={pt:5}   pt-BR markers={br:5}"
          f"  -> {'pt-PT (European)' if pt > br else 'pt-BR (Brazilian)'}")
    for kk, vv in pairs[k][:1]:
        pass
    print(f"     e.g. ABANDON_CONFIRM_BODY = "
          f"{dict(pairs[k]).get('ABANDON_CONFIRM_BODY','')[:80]!r}")
    print(f"          ABANDON_CONFIRM_HEADER = "
          f"{dict(pairs[k]).get('ABANDON_CONFIRM_HEADER','')[:60]!r}")

print("\n" + "=" * 78)
print("D) SPANISH variants: variant_14 (span 120) vs variant_18 (span 168)")
print("=" * 78)
for k in (14, 18):
    txt = " ".join(v for _, v in pairs[k][:20000]).lower()
    es = sum(txt.count(t) for t in (" vosotros ", " os ", "áis ", "éis ", " vuestro ", " ordenador ", " coche "))
    la = sum(txt.count(t) for t in (" ustedes ", " computadora ", " celular ", " carro ", " agarra "))
    print(f"  variant_{k:02d} span={meta[k]['span']}   es-ES markers={es:5}   es-419 markers={la:5}")
    print(f"     ABANDON_CONFIRM_BODY = {dict(pairs[k]).get('ABANDON_CONFIRM_BODY','')[:85]!r}")

print("\n" + "=" * 78)
print("E) how many entries are IDENTICAL to English in each variant (untranslated tail)")
print("=" * 78)
en = [v for _, v in pairs[0]]
for k in sorted(pairs):
    same = sum(1 for i in range(N) if pairs[k][i][1] == en[i])
    print(f"  variant_{k:02d} span={meta[k]['span']:>3} {meta[k]['lang']:<22} "
          f"same_as_EN={same:>6} ({100*same/N:5.1f}%)")
