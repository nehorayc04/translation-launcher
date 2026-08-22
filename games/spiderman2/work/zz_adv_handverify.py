"""Hand-verify the 15 most-mixed descriptions char-by-char, and re-derive whether
the '206 first-Hebrew-on-right' flags are real or a heuristic artifact.
"""
import json, os, re
from bidi.algorithm import get_display

HERE = os.path.dirname(os.path.abspath(__file__))
RLM = "‏"; LRM="‎"
WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")

def has_heb(s): return any("א" <= c <= "ת" for c in s)
def has_lat(s): return any(("A"<=c<="Z") or ("a"<=c<="z") for c in s)
def strip_inner_markup(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;", "", s)
    return s
def vis(s, base):
    return "\n".join(get_display(p, base_dir=base) for p in re.split(r"[\n\r]", s))

descs = {}
for fn in ["settings_he.json"] + [f"menus{n}_he.json" for n in range(2,14)] + ["menus_he.json"]:
    p = os.path.join(HERE, fn)
    if not os.path.exists(p): continue
    for k,v in json.load(open(p,encoding="utf-8")).items():
        if isinstance(v,str) and v.startswith(RLM) and has_heb(v):
            descs.setdefault(k,v)

# rank by mixedness: count of latin words * has punctuation
def mixscore(t):
    return len(WORD.findall(t)) + (3 if re.search(r"[()\[\]:.!?,]", t) else 0)

rows=[]
for k,raw in descs.items():
    t = strip_inner_markup(raw[len(RLM):])
    if has_lat(t) and has_heb(t):
        rows.append((mixscore(t), k, t))
rows.sort(reverse=True)

print("===== TOP 15 MOST-MIXED — char-by-char =====\n")
for score,k,t in rows[:15]:
    vR = vis(RLM+t, "R")
    print(f"### {k}  (score {score})")
    print(f"  LOGICAL : {t}")
    print(f"  RTLVIS  : {vR.replace(RLM,'').replace(LRM,'')}")
    # confirm each latin word + number present
    miss=[w for w in WORD.findall(t) if w not in vR]
    print(f"  latin words: {WORD.findall(t)}")
    print(f"  MISSING in visual: {miss if miss else 'none'}")
    print()

# ---- Re-derive the '206 first-Hebrew-on-right' flags from 90_bidi_sim.py ----
# Replicate that script's bad_first logic EXACTLY, then judge each flag.
print("\n===== RE-DERIVE 'first-Hebrew-on-right' flags (90_bidi_sim.py logic) =====")
bad_first=[]
for k,raw in descs.items():
    t = strip_inner_markup(raw[len(RLM):])
    vR = vis(RLM+t,"R"); vL = vis(t,"L")
    mixed = bool(WORD.search(t)) and has_heb(t)
    if has_heb(t):
        first_heb = next(c for c in t if "א"<=c<="ת")
        vRc = vR.replace(RLM,"")
        pos = vRc.find(first_heb)
        if pos != -1 and pos < len(vRc)*0.4 and mixed:
            bad_first.append((k,pos,len(vRc),t,vRc))
print(f"flagged count: {len(bad_first)}")
print("\n--- inspect first 12 flagged: is the FIRST logical Hebrew word actually on the right? ---")
for k,pos,ln,t,vRc in bad_first[:12]:
    # In a correct RTL render the text STARTS (reads) from the right. The first
    # logical word should appear at the RIGHT edge of the visual = HIGH index.
    # When a description begins with a LATIN word/number, the first Hebrew char
    # legitimately sits left of that leading L-run -> low index is EXPECTED, not a bug.
    leads_latin = bool(re.match(r"^\s*[A-Za-z0-9]", t))
    print(f"  {k}: first-heb idx {pos}/{ln}  leads_with_latin={leads_latin}")
    print(f"     LOGICAL: {t[:80]}")
    print(f"     RTLVIS : {vRc[:80]}")
print(f"\nof {len(bad_first)} flagged, leads_with_latin = "
      f"{sum(1 for x in bad_first if re.match(r'^[\\s]*[A-Za-z0-9]', x[3]))}")
