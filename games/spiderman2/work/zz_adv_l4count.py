"""Quantify L4 dependence among the DESCRIPTIONS (the dimension under test).
A bracket whose content is LATIN ([ACTION_X], (HUD)) is part of an LTR run -> its
internal order and glyphs are preserved regardless of L4. A bracket whose content
is HEBREW (or empty) resolves to RTL level -> its glyph depends on cohtml L4
mirroring to look correct. Count how many of the 1434 RLM+plain descriptions have
a Hebrew-content paren, and list them."""
import json, os, re
HERE=os.path.dirname(os.path.abspath(__file__))
RLM="‏"
def has_heb(s): return any("א"<=c<="ת" for c in s)
def strip(s):
    s=re.sub(r"<[^>]+>","",s); s=re.sub(r"&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;","",s); return s

descs={}
for fn in ["settings_he.json"]+[f"menus{n}_he.json" for n in range(2,14)]+["menus_he.json"]:
    p=os.path.join(HERE,fn)
    if not os.path.exists(p): continue
    for k,v in json.load(open(p,encoding="utf-8")).items():
        if isinstance(v,str) and v.startswith(RLM) and has_heb(v): descs.setdefault(k,v)

heb_paren_desc=[]
lat_paren_desc=0
for k,raw in descs.items():
    t=strip(raw[len(RLM):])
    has_heb_p=False; has_lat_p=False
    for m in re.finditer(r"[()\[\]]", t):
        pass
    for m in re.finditer(r"[(\[]([^)\]]{0,40})[)\]]", t):
        inner=m.group(1)
        if re.search(r"[א-ת]", inner): has_heb_p=True
        elif re.search(r"[A-Za-z0-9]", inner): has_lat_p=True
    if has_heb_p: heb_paren_desc.append((k,t[:70]))
    if has_lat_p: lat_paren_desc+=1

print(f"descriptions total: {len(descs)}")
print(f"  with LATIN-content bracket (L4-independent, safe): {lat_paren_desc}")
print(f"  with HEBREW-content bracket (depends on cohtml L4): {len(heb_paren_desc)}")
for k,t in heb_paren_desc[:30]:
    print(f"    {k}: {t}")
