#!/usr/bin/env python3
import sys, re, json
sys.path.insert(0, r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/ghost_of_tsushima/tools")
import xpps_alt as X

EN = r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/ghost_of_tsushima/extract/lang_english_text.xpps"
AR = r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/ghost_of_tsushima/extract/lang_arabic_text.xpps"

men = X.read_pack(EN)         # {key_hex: text}
mar = X.read_pack(AR)
he, ha = set(men), set(mar)
ov = he & ha
print(f"EN records={len(men)}  AR records={len(mar)}  overlap(exact key)={len(ov)}")
print(f"EN-only={len(he-ha)}  AR-only={len(ha-he)}")

# split by key kind
def big(k): return int(k, 16) > 0x1_0000_0000
big_ov = [k for k in ov if big(k)]
small_ov = [k for k in ov if not big(k)]
print(f"overlap large-hash={len(big_ov)}  overlap small-id={len(small_ov)}")

# translation status on overlap
same = sum(1 for k in ov if men[k] == mar[k])
arab = sum(1 for k in ov if re.search(r'[؀-ۿ]', mar[k]))
print(f"overlap: AR==EN(untranslated names/codes)={same}  AR-has-arabic={arab}")

# tokens
toks = {}
for v in men.values():
    for m in re.findall(r'\{[A-Z_0-9]+\}|%[0-9.lhd]*[sdfxXe]|\\n', v):
        toks[m] = toks.get(m, 0) + 1
pua = set()
for v in men.values():
    for ch in v:
        if 0xE000 <= ord(ch) <= 0xF8FF:
            pua.add(ch)
print(f"\ncurly/printf tokens: {sorted(toks.items(), key=lambda x:-x[1])[:12]}")
print(f"PUA glyphs distinct={len(pua)} sample={[hex(ord(c)) for c in sorted(pua)[:14]]}")
newl = sum(1 for v in men.values() if '\n' in v)
print(f"strings containing literal newline: {newl}")

# scope UI vs subtitle (large-hash=UI/content; small-id=dialogue/subs)
ui = sum(1 for k in men if big(k))
subs = sum(1 for k in men if not big(k))
# refine: among large-hash, long sentence-ish = content/subtitle-like
longish = sum(1 for k, v in men.items() if big(k) and len(v.split()) >= 8)
print(f"\nscope: large-hash(UI/menus/content)={ui}  small-id(dialogue/subtitle blocks)={subs}")
print(f"  of large-hash, >=8 words (sentence/subtitle-like)={longish}")

# samples: 10 matched triples, varied
print("\n=== SAMPLE TRIPLES (id, en, ar) ===")
import random; random.seed(7)
picks = []
# some UI + some with tokens + some dialogue
want = [k for k in big_ov if men[k] in ('Options','Subtitles','New Game','Continue')]
want += [k for k in big_ov if '' in men[k]][:2]
want += [k for k in big_ov if '%' in men[k]][:1]
want += random.sample(big_ov, 4)
want += random.sample(small_ov, 3) if small_ov else []
seen = set()
samples = []
for k in want:
    if k in seen: continue
    seen.add(k)
    samples.append({"id": k, "en": men[k], "ar": mar[k]})
for s in samples[:12]:
    print(f"  {s['id']}  EN={s['en'][:55]!r}  AR={s['ar'][:55]!r}")

# dump samples json for the schema
with open(r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/ghost_of_tsushima/tools/_samples.json","w",encoding="utf-8") as f:
    json.dump(samples[:12], f, ensure_ascii=False, indent=1)
