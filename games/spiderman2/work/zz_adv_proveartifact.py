"""Prove the '206 first-Hebrew-on-right' flags are a str.find() artifact, not a
render defect. The 90_bidi_sim heuristic does vRc.find(first_heb) where first_heb
is a single CHAR; .find returns the earliest L->R occurrence of that char, which
is almost always an INTERIOR repeat, not the first logical word's position.

Correct test: the first LOGICAL WORD (whole word) of a Hebrew-initial string
should sit at the RIGHT edge of the RTL visual. Verify that instead.
"""
import json, os, re
from bidi.algorithm import get_display
HERE = os.path.dirname(os.path.abspath(__file__))
RLM="‏"
def has_heb(s): return any("א"<=c<="ת" for c in s)
def strip(s):
    s=re.sub(r"<[^>]+>","",s); s=re.sub(r"&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;","",s); return s
def vis(s,b): return "\n".join(get_display(p,base_dir=b) for p in re.split(r"[\n\r]",s))
WORD=re.compile(r"[A-Za-z][A-Za-z0-9]*")
HEBWORD=re.compile(r"[א-ת]+")

descs={}
for fn in ["settings_he.json"]+[f"menus{n}_he.json" for n in range(2,14)]+["menus_he.json"]:
    p=os.path.join(HERE,fn)
    if not os.path.exists(p): continue
    for k,v in json.load(open(p,encoding="utf-8")).items():
        if isinstance(v,str) and v.startswith(RLM) and has_heb(v): descs.setdefault(k,v)

real_defect=0; artifact=0; examined=0
defects=[]
for k,raw in descs.items():
    t=strip(raw[len(RLM):])
    mixed=bool(WORD.search(t)) and has_heb(t)
    if not (has_heb(t) and mixed): continue
    # only the strings the old heuristic flagged
    first_heb=next(c for c in t if "א"<=c<="ת")
    vRc=vis(RLM+t,"R").replace(RLM,"")
    pos=vRc.find(first_heb)
    if not (pos!=-1 and pos<len(vRc)*0.4):
        continue
    examined+=1
    # Does the string LOGICALLY start with a Hebrew word (ignoring leading spaces)?
    lead=t.lstrip()
    starts_heb = bool(re.match(r"^[א-ת]", lead))
    # Where does the FIRST WHOLE Hebrew word land in the visual?
    m=HEBWORD.search(t)
    firstword=m.group(0) if m else ""
    # In the visual it appears reversed:
    fw_vis=firstword[::-1]
    widx=vRc.find(fw_vis)
    on_right = widx!=-1 and (widx+len(fw_vis)) >= len(vRc.rstrip())*0.6
    if starts_heb and not on_right:
        real_defect+=1; defects.append((k,t[:60],vRc[:60]))
    else:
        artifact+=1

print(f"examined (old-heuristic-flagged): {examined}")
print(f"  -> ARTIFACT (first Hebrew WORD actually on the right / or string starts w/ bracket-token): {artifact}")
print(f"  -> REAL DEFECT (Hebrew-initial but first word NOT on right): {real_defect}")
for d in defects[:20]:
    print("   DEFECT", d)
