# -*- coding: utf-8 -*-
"""Merge the Google agent's tail translations back into the SM2 spine.
Reads gemini_tail_input.json (now Hebrew, with @@TSn@@ markers) + gemini_tail_src.json,
reattaches the real <ts="..."> tags, validates structurally, writes into
subtitles_he.json (ts entries) / dialogue_he.json (plain), drops the 12 from skip."""
import json, os, re, shutil, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

W = os.path.dirname(os.path.abspath(__file__))
inp  = json.load(open(os.path.join(W, "gemini_tail_input.json"), encoding="utf-8"))
src  = json.load(open(os.path.join(W, "gemini_tail_src.json"), encoding="utf-8"))

TS_RE   = re.compile(r'<ts="[^"]*">')
TS_PH   = re.compile(r'@@TS(\d+)@@')
BAD     = re.compile(r'[؀-ۿЀ-ӿͰ-Ͽ฀-๿ऀ-ॿ一-鿿가-힯]')
NIQQUD  = re.compile(r'[֑-ׇ]')

def reattach(en, he):
    tags = TS_RE.findall(en)
    return TS_PH.sub(lambda m: tags[int(m.group(1))-1] if 1 <= int(m.group(1)) <= len(tags) else m.group(0), he)

subp = os.path.join(W, "subtitles_he.json")
dialp = os.path.join(W, "dialogue_he.json")
subs = json.load(open(subp, encoding="utf-8"))
dial = json.load(open(dialp, encoding="utf-8"))

ok, bad = [], []
to_subs, to_dial = {}, {}
for k, he in inp.items():
    en = src[k]["en"]
    he2 = reattach(en, he)
    # structural gates
    if not re.search(r'[א-ת]', he2):           bad.append((k, "no Hebrew")); continue
    if BAD.search(he2):                         bad.append((k, "foreign script")); continue
    if NIQQUD.search(he2):                      bad.append((k, "niqqud")); continue
    if "@@TS" in he2:                           bad.append((k, "unresolved @@TS marker")); continue
    if sorted(TS_RE.findall(en)) != sorted(TS_RE.findall(he2)):
        bad.append((k, "ts mismatch")); continue
    if TS_RE.search(en):  to_subs[k] = he2
    else:                 to_dial[k] = he2
    ok.append(k)

if bad:
    print("VALIDATION FAILURES (not merged):")
    for k, why in bad: print(f"  {k}: {why}")
if not ok:
    print("Nothing valid to merge — fix the failures above and re-run.")
    sys.exit(1)

shutil.copyfile(subp, subp + ".bak_tailmerge")
shutil.copyfile(dialp, dialp + ".bak_tailmerge")
subs.update(to_subs); dial.update(to_dial)
for path, data in ((subp, subs), (dialp, dial)):
    json.dump(data, open(path + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.replace(path + ".tmp", path)

# drop the merged keys from skip
skipp = os.path.join(W, "sm2_translate_skip.json")
skip = json.load(open(skipp, encoding="utf-8"))
is_list = isinstance(skip, list)
keys = list(skip)
newk = [x for x in keys if x not in ok]
shutil.copyfile(skipp, skipp + ".bak_tailmerge")
out = newk if is_list else {x: skip[x] for x in newk}
json.dump(out, open(skipp + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
os.replace(skipp + ".tmp", skipp)

print(f"MERGED {len(ok)} entries  (subtitles_he +{len(to_subs)}, dialogue_he +{len(to_dial)})")
print(f"skip-list: {len(keys)} -> {len(newk)}")
print("OK keys:", ", ".join(ok))
