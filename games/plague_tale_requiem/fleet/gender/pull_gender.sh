#!/bin/bash
# Gender-review pull+merge: pull each free stream's out.json (proposed gender-corrected Hebrew),
# then SAFELY merge into ../hebrew.json. A proposal is accepted ONLY when it is a pure gender
# inflection of the current line (identical non-Hebrew scaffold + each changed Hebrew word is
# inflection-scale, lev<=3) -> a paraphrase / degradation is rejected and the original stays.
# PT translation is already 100% and PTFleetPull is disabled, so ../hebrew.json is the authority here.
KEY=~/.ssh/id_ed25519
HERE="/c/Users/Nehoray_Cohen/Projects/Game translator/games/plague_tale_requiem/fleet/gender"
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/plague_tale_requiem/fleet"
GB="$HERE/gbanks"; mkdir -p "$GB"
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
LOG=/c/tmp/pt_gender_pull.log
LOCK=/c/tmp/pt_gender_pull.lock
if [ -f "$LOCK" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  [ "$age" -lt 150 ] && exit 0
fi
touch "$LOCK"
pull(){ # name port
  local dest="$GB/out_$1.json"; local tmp="$dest.tmp"; rm -f "$tmp"
  timeout 40 scp -i "$KEY" -P "$2" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20 "vboxuser@127.0.0.1:C:/ptwg/out.json" "$tmp" 2>/dev/null
  if [ -s "$tmp" ] && "$PY" -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$tmp" 2>/dev/null; then mv -f "$tmp" "$dest"; else rm -f "$tmp"; fi
}
pull vm  2222
pull vm2 2223
# desktop is LOCAL
DW="$HERE/desktop/out.json"
if [ -s "$DW" ] && "$PY" -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$DW" 2>/dev/null; then cp -f "$DW" "$GB/out_desktop.json"; fi

FLEETWIN="$(cygpath -w "$FLEET")"; HEREWIN="$(cygpath -w "$HERE")"
"$PY" -X utf8 - <<PYEOF >> "$LOG" 2>&1
import json,os,glob,re,time
FLEET=r"$FLEETWIN"; HERE=r"$HEREWIN"; GB=os.path.join(HERE,"gbanks")
HEBP=os.path.join(FLEET,"hebrew.json")
NIQ=re.compile(r'[֑-ֽֿׁׂ]'); FOREIGN=re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]')
STRUCT=re.compile(r'\{[^}]*\}|\||%%|%[#0-9.*\-+]*[a-zA-Z]+'); HEBRUN=re.compile(r'[֐-׿]+')
def scaffold(s): return re.sub(r'[֐-׿]','',s)          # everything EXCEPT Hebrew letters
def words(s): return HEBRUN.findall(s)
def lev(a,b):
    if a==b: return 0
    m,n=len(a),len(b); prev=list(range(n+1))
    for i in range(1,m+1):
        cur=[i]+[0]*n
        for j in range(1,n+1):
            cur[j]=min(prev[j]+1,cur[j-1]+1,prev[j-1]+(a[i-1]!=b[j-1]))
        prev=cur
    return prev[n]
def safe(old,new):
    if not isinstance(new,str) or not new.strip() or new==old: return False
    if NIQ.search(new) or FOREIGN.search(new): return False
    if sorted(STRUCT.findall(new))!=sorted(STRUCT.findall(old)): return False
    if scaffold(new)!=scaffold(old): return False       # only Hebrew letters may change
    ow,nw=words(old),words(new)
    if len(ow)!=len(nw): return False                    # (guaranteed by scaffold, belt+braces)
    for a,b in zip(ow,nw):
        if a!=b and lev(a,b)>3: return False             # each change must be inflection-scale
    return True
try: name_fixes=json.load(open(os.path.join(FLEET,"name_fixes.json"),encoding="utf-8"))
except Exception: name_fixes=[]
def canon(v):
    for w,r in name_fixes: v=v.replace(w,r)
    return v
heb=json.load(open(HEBP,encoding="utf-8"))
# one-time backup before the FIRST gender edit
bak=HEBP+".bak.gender"
if not os.path.exists(bak): json.dump(heb,open(bak,"w",encoding="utf-8"),ensure_ascii=False)
prop={}
for f in glob.glob(os.path.join(GB,"out_*.json")):
    try:
        for k,v in json.load(open(f,encoding="utf-8")).items():
            if isinstance(v,str) and v.strip(): prop[k]=v
    except Exception: pass
changed=0; reviewed=len(prop)
for k,newhe in prop.items():
    old=heb.get(k)
    if not isinstance(old,str): continue
    cand=canon(newhe)
    if safe(old,cand):
        heb[k]=cand; changed+=1
tmp=HEBP+".tmp"; json.dump(heb,open(tmp,"w",encoding="utf-8"),ensure_ascii=False); os.replace(tmp,HEBP)
# durable overlay: every gender-corrected value vs the pre-gender baseline -> gender_overrides.json
# pull_pt.sh re-applies this AFTER its bank-rebuild, so a concurrent PT pull can never wipe the fixes.
try: base=json.load(open(bak,encoding="utf-8"))
except Exception: base={}
ov={k:heb[k] for k in heb if isinstance(heb[k],str) and heb[k]!=base.get(k)}
ovp=os.path.join(FLEET,"gender_overrides.json"); ovt=ovp+".tmp"
json.dump(ov,open(ovt,"w",encoding="utf-8"),ensure_ascii=False); os.replace(ovt,ovp)
print(f"{time.strftime('%F %H:%M:%S')}  gender: reviewed {reviewed} | accepted-changes {changed} | hebrew.json={len(heb)} | overrides={len(ov)}")
PYEOF
tail -1 "$LOG"
rm -f "$LOCK"
