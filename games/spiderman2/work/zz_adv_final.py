"""Final checks:
 1. printf placeholders (%d %s %1$s etc) present + count-preserved logical vs the
    Arabic source (bidi can't change logical bytes, but confirm the TRANSLATION
    didn't drop/add them — a real bug source).
 2. The '!®'/'®!' ordering: hand-read ANALYTICS_POPUP_DESC_0 first line.
 3. Confirm every [ACTION_*]/[BTN_*] token survives verbatim in the RTL visual
    (these are the bracket-tokens; a split would break the on-screen button glyph).
"""
import json, os, re
from bidi.algorithm import get_display
HERE=os.path.dirname(os.path.abspath(__file__))
RLM="‏"
def strip(s):
    s=re.sub(r"<[^>]+>","",s); s=re.sub(r"&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;","",s); return s
def visline(s,b): return get_display(s,base_dir=b).replace(RLM,"")

raws={}
for fn in ["settings_he.json"]+[f"menus{n}_he.json" for n in range(2,14)]+["menus_he.json"]:
    p=os.path.join(HERE,fn)
    if not os.path.exists(p): continue
    for k,v in json.load(open(p,encoding="utf-8")).items():
        if isinstance(v,str): raws.setdefault(k,v)

# 1. bracket-token integrity across ALL values (the [ACTION_*] glyph tokens)
TOK=re.compile(r"\[[A-Z0-9_]+\]")
split=0; splitex=[]
for k,v in raws.items():
    t=strip(v[len(RLM):] if v.startswith(RLM) else (v.replace("‫","").replace("‬","")))
    vr=visline(RLM+t,"R")
    for tok in TOK.findall(t):
        if tok not in vr:
            split+=1; splitex.append((k,tok,vr[:50]))
print(f"[1] bracket-token [ACTION_*]/[BTN_*] integrity: {split} split out of all values")
for e in splitex[:15]: print("    SPLIT:", e)

# 2. printf placeholder integrity within each value (just confirm they exist & are
#    contiguous %s/%d/%u/%1$s/%% in the logical string)
PH=re.compile(r"%(?:\d+\$)?[sdufgxX%]")
ph_total=sum(len(PH.findall(v)) for v in raws.values())
print(f"\n[2] total printf placeholders across values: {ph_total}")
# show the %d/%s entries and confirm placeholder not broken by a stray space
brk=[(k,v) for k,v in raws.items() if re.search(r"%\s+[sd]|%[sd][א-ת]", strip(v))]
print(f"    placeholders glued to Hebrew or space-broken: {len(brk)}")
for k,v in brk[:10]: print("    ", k, repr(strip(v))[:70])

# 3. ANALYTICS '!®' first sentence hand-read
k="ANALYTICS_POPUP_DESC_0"
t=strip(raws[k][len(RLM):])
first=t.split("!")[0]+"!"
print(f"\n[3] {k} first sentence logical:\n    {first}")
print(f"    RTL visual:\n    {visline(RLM+first,'R')}")
print("    -> reading the visual right-to-left, '®' should sit with 'PlayStation' and '!' end the clause")
