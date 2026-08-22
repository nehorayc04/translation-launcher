"""Hand-verify parenthetical rendering: (a) Latin-content parens like (HUD)/(ASL)
read correctly; (b) any HEBREW-content parens — where bracket mirroring matters —
render with the open paren on the correct (right) side.
"""
import json, os, re
from bidi.algorithm import get_display
HERE=os.path.dirname(os.path.abspath(__file__))
RLM="‏"
def strip(s):
    s=re.sub(r"<[^>]+>","",s); s=re.sub(r"&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;","",s); return s
def vis(s,b): return "\n".join(get_display(p,base_dir=b) for p in re.split(r"[\n\r]",s)).replace(RLM,"")

raws={}
for fn in ["settings_he.json"]+[f"menus{n}_he.json" for n in range(2,14)]+["menus_he.json"]:
    p=os.path.join(HERE,fn)
    if not os.path.exists(p): continue
    for k,v in json.load(open(p,encoding="utf-8")).items():
        if isinstance(v,str): raws.setdefault(k,v)

# Hebrew-content parenthetical: '(' immediately followed by a Hebrew char
heb_paren=[]
lat_paren=[]
for k,v in raws.items():
    t=strip(v[len(RLM):] if v.startswith(RLM) else v.replace("‫","").replace("‬",""))
    for m in re.finditer(r"\(([^)]{1,40})\)", t):
        inner=m.group(1)
        if re.search(r"[א-ת]", inner): heb_paren.append((k,m.group(0)))
        elif re.search(r"[A-Za-z]", inner): lat_paren.append((k,m.group(0)))

print(f"Hebrew-content parentheticals: {len(heb_paren)}  |  Latin-content: {len(lat_paren)}")
print("\n--- HEBREW-content parens (bracket-mirror matters) — hand-verify 12 ---")
seen=set()
for k,seg in heb_paren:
    if seg in seen: continue
    seen.add(seg)
    # build a tiny RTL context: Hebrew word + the paren
    demo="מילה "+seg+" סוף"
    print(f"  {k}: {seg!r}")
    print(f"     in-context VIS: {vis(RLM+demo,'R')!r}")
    if len(seen)>=12: break

print("\n--- a couple Latin-content (HUD)/(ASL) full lines ---")
for kk in ["SETTING_HIDEHUD_DESC","SETTING_NARRATEDASL_DESC"]:
    v=raws.get(kk)
    if v:
        t=strip(v[len(RLM):] if v.startswith(RLM) else v)
        print(f"  {kk}: VIS {vis(RLM+t,'R')[:70]!r}")
