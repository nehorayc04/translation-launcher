"""Build the FULL CP2077 dual-gender community-pool dataset.
Emits cp2077_dualgender.json = { "section|key": {source_en, he_female, he_male, current_he(before), section} }
for every translatable spine entry (onscreens_final + subtitles + DLC), dedup'd (drops the
onscreens.json mirror in favour of onscreens_final.json). Categories are derived server-side from `section`.

Key field per entry: primaryKey (onscreens + BASE subtitles) OR stringId (DLC subtitles).
EN source: full_pool[sec|key] -> localization_export (base onscreens) / dlc_ep1_text (DLC, by stringId)
           -> the HE entry's own secondaryKey (BASE subtitles carry the English there).
"""
import json, os, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
RES = os.path.join(ROOT, "תרגום_משחקים", "source", "resources")
HE_BASE = os.path.join(RES, "localization_translated.json")
HE_DLC  = os.path.join(RES, "dlc_ep1_translated.json")
EN_BASE = os.path.join(RES, "localization_export.json")
EN_DLC  = os.path.join(RES, "dlc_ep1_text.json")
BEFORE  = os.path.join(RES, "localization_translated.json.bak.trunc.20260614_080231")
FULLPOOL= os.path.join(HERE, "agent_handoff_qa", "_pool", "full_pool.json")
OUT = os.path.join(HERE, "cp2077_dualgender.json")
HEB = re.compile(r'[֐-׿]')

def jl(p):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception as e: print("  load-fail", os.path.basename(p), e); return {}

def entry_key(e):
    pk = e.get("primaryKey")
    return str(pk) if pk is not None else str(e.get("stringId"))

def index(d):
    idx = {}
    for sec, rows in d.items():
        if not isinstance(rows, list): continue
        m = {}
        for e in rows:
            if isinstance(e, dict): m[entry_key(e)] = e
        idx[sec] = m
    return idx

print("loading HE spine..."); he = jl(HE_BASE); hed = jl(HE_DLC)
print("loading EN sources..."); en = index(jl(EN_BASE)); end = index(jl(EN_DLC))
print("loading full_pool..."); fp = jl(FULLPOOL)
print("loading BEFORE backup..."); bfb = index(jl(BEFORE))

def en_for(sec, kid, he_entry):
    k = f"{sec}|{kid}"
    if (fp.get(k) or "").strip(): return fp[k]
    e = en.get(sec, {}).get(kid) or end.get(sec, {}).get(kid)
    if e:
        v = (e.get("femaleVariant") or e.get("maleVariant") or "").strip()
        if v: return v
    return (he_entry.get("secondaryKey") or "").strip()   # BASE subtitles: EN lives here

def before_for(sec, kid):
    e = bfb.get(sec, {}).get(kid)
    return (e.get("femaleVariant") or "").strip() if e else ""

out = {}
stats = dict(total=0, has_en=0, has_before=0, fdiff=0)
def emit(d):
    for sec, rows in d.items():
        if not isinstance(rows, list): continue
        if sec.split("/")[-1] == "onscreens.json": continue   # dedup mirror; keep onscreens_final
        for e in rows:
            if not isinstance(e, dict): continue
            f = (e.get("femaleVariant") or "").strip(); m = (e.get("maleVariant") or "").strip()
            if not (f or m) or not (HEB.search(f) or HEB.search(m)): continue
            kid = entry_key(e); key = f"{sec}|{kid}"
            source_en = en_for(sec, kid, e); before = before_for(sec, kid)
            out[key] = {"source_en": source_en, "he_female": f, "he_male": m,
                        "current_he": before if before and before != f else "", "section": sec}
            stats["total"] += 1
            if source_en: stats["has_en"] += 1
            if out[key]["current_he"]: stats["has_before"] += 1
            if f != m: stats["fdiff"] += 1
emit(he); emit(hed)
# drop rows with no English source (can't show a split without the sentence)
noen = [k for k, v in out.items() if not v["source_en"].strip()]
for k in noen: del out[k]
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("=" * 50)
print(f"kept {len(out)} rows (dropped {len(noen)} no-EN) -> {OUT}")
print(f"  f!=m (gendered split): {sum(1 for v in out.values() if v['he_female']!=v['he_male'])}")
print(f"  has-before(distinct):  {sum(1 for v in out.values() if v['current_he'])}")
from collections import Counter
print("  section roots:", dict(Counter(k.split('/')[0] for k in out).most_common()))
