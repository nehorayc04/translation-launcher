"""Hunt the genuinely risky bidi cases:
 (a) sentence-final punctuation that is ADJACENT to a Latin/number run (where
     UBA may place it on the visually-wrong side),
 (b) strings ENDING in a Latin token (logical end => visual LEFT) — these read
     'last' and a trailing '.'/'!' may detach,
 (c) the '!®' / '®!' ordering in ANALYTICS_POPUP,
 (d) any literal &rlm;/&lrm; entities (cohtml entity-decode question).
"""
import json, os, re
from bidi.algorithm import get_display
HERE=os.path.dirname(os.path.abspath(__file__))
RLM="‏"
def has_heb(s): return any("א"<=c<="ת" for c in s)
def has_lat(s): return any(("A"<=c<="Z") or ("a"<=c<="z") for c in s)
def strip(s):
    s=re.sub(r"<[^>]+>","",s); s=re.sub(r"&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;","",s); return s
def visline(s,b): return get_display(s,base_dir=b).replace(RLM,"")

descs={}
raws={}
for fn in ["settings_he.json"]+[f"menus{n}_he.json" for n in range(2,14)]+["menus_he.json"]:
    p=os.path.join(HERE,fn)
    if not os.path.exists(p): continue
    for k,v in json.load(open(p,encoding="utf-8")).items():
        if isinstance(v,str):
            raws.setdefault(k,v)
            if v.startswith(RLM) and has_heb(v): descs.setdefault(k,v)

print("=== (d) literal &rlm;/&lrm;/&#x200F; entities in ANY value ===")
ent=[(k,v) for k,v in raws.items() if re.search(r"&rlm;|&lrm;|&#x?200[EF];|&#820[6-9];", v, re.I)]
for k,v in ent: print(f"   {k}: {v!r}")
print(f"   total: {len(ent)}")

print("\n=== (b) descriptions whose LOGICAL text ENDS with a Latin token or number ===")
trail=[]
for k,raw in descs.items():
    t=strip(raw[len(RLM):]).rstrip()
    if re.search(r"[A-Za-z0-9][\.\!\?\)]*$", t) and has_heb(t):
        trail.append((k,t))
for k,t in trail[:30]:
    vr=visline(RLM+t,"R")
    print(f"   {k}")
    print(f"      LOG: ...{t[-40:]!r}")
    print(f"      VIS(left edge read last): {vr[:40]!r}")
print(f"   total trailing-latin/num: {len(trail)}")

print("\n=== (c) ANALYTICS_POPUP '!®' ordering + any '®!'/'!®' ===")
for k,raw in raws.items():
    if "®" in raw and re.search(r"[!?.]®|®[!?.]", raw):
        t=strip(raw[len(RLM):] if raw.startswith(RLM) else raw)
        vr=visline(RLM+t,"R") if (raw.startswith(RLM)) else get_display(t,base_dir="R")
        # show the snippet around ®
        i=t.find("®")
        print(f"   {k}: around-® logical={t[max(0,i-8):i+3]!r}")
        j=vr.find("®")
        print(f"      visual around-® ={vr[max(0,j-8):j+8]!r}")

print("\n=== (a) punctuation directly adjacent to Latin run, mid-Hebrew ===")
risky=[]
for k,raw in descs.items():
    t=strip(raw[len(RLM):])
    # find e.g. 'word.' or '.word' or ':word' where word is latin and Hebrew around
    for m in re.finditer(r"[A-Za-z0-9]+[\.\:\!\?][֐-׿]|[֐-׿][\.\:\!\?][A-Za-z0-9]+", t):
        risky.append((k,m.group(0)))
        break
for k,seg in risky[:25]:
    print(f"   {k}: {seg!r}")
print(f"   total adjacency cases: {len(risky)}")
