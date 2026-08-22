"""Revert the fleet's English-leak regressions: any spine entry whose femaleVariant is
'mostly English' (the AI left the source untranslated with a stray Hebrew char + control byte)
is reverted to the GOOD pre-fleet Hebrew from the 2026-06-14 backup (set BOTH variants).
Backs up the spine first. Reports counts + sections. DLC has no pre-fleet backup here → its
broken lines are listed (handled as 'open' in the /translate pool)."""
import json, os, re, sys, time, shutil
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
RES = os.path.join(ROOT, "תרגום_משחקים", "source", "resources")
HE_BASE = os.path.join(RES, "localization_translated.json")
HE_DLC  = os.path.join(RES, "dlc_ep1_translated.json")
BEFORE  = os.path.join(RES, "localization_translated.json.bak.trunc.20260614_080231")
HEB = re.compile(r'[֐-׿]'); LAT = re.compile(r'[A-Za-z]{2,}')
TOK = re.compile(r'<[^>]*>|\{[^}]*\}|\[[^\]]*\]|&\w+;|%\w')
def broken(s):
    core = TOK.sub('', s or ''); lat = len(LAT.findall(core)); heb = len(HEB.findall(core))
    return lat >= 3 and heb <= lat * 0.5
def good_heb(s):
    return bool(s) and not broken(s) and HEB.search(s or '')
def ekey(e):
    pk = e.get("primaryKey"); return str(pk) if pk is not None else str(e.get("stringId"))

def jl(p):
    return json.load(open(p, encoding="utf-8"))

print("loading..."); base = jl(HE_BASE); dlc = jl(HE_DLC); bfb = jl(BEFORE)
# index backup by section|key
bidx = {}
for sec, rows in bfb.items():
    if isinstance(rows, list):
        for e in rows:
            if isinstance(e, dict): bidx[f"{sec}|{ekey(e)}"] = (e.get("femaleVariant") or "")

from collections import Counter
fixed = 0; unfixable = 0; secs = Counter(); dry = "--apply" not in sys.argv
for d, tag in ((base, "base"), (dlc, "dlc")):
    for sec, rows in d.items():
        if not isinstance(rows, list): continue
        for e in rows:
            if not isinstance(e, dict): continue
            f = e.get("femaleVariant") or ""
            if not broken(f): continue
            bv = bidx.get(f"{sec}|{ekey(e)}", "")
            if good_heb(bv):
                if not dry:
                    e["femaleVariant"] = bv; e["maleVariant"] = bv
                fixed += 1; secs[sec.split("/")[0]] += 1
            else:
                unfixable += 1
print(f"broken→revertable(good before): {fixed} | broken w/o good before: {unfixable}")
print("fixed sections:", dict(secs))
if dry:
    print("\nDRY RUN — re-run with --apply to write (backs up the spine).")
else:
    ts = time.strftime("%Y%m%d_%H%M%S")
    for p in (HE_BASE, HE_DLC):
        shutil.copy2(p, p + f".bak.engleak.{ts}")
    for p, d in ((HE_BASE, base), (HE_DLC, dlc)):
        tmp = p + ".tmp"; json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False); os.replace(tmp, p)
    print(f"APPLIED + backed up (.bak.engleak.{ts})")
