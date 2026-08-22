"""Validate a Claude-translated dual-gender batch {key:{f,m}} and merge into the Claude bank.
EN source = C:\\tmp\\claude_translate.json. Rejects: missing key, token mismatch vs EN, foreign
script, niqqud, no Hebrew on real prose, empty. Rejected keys are printed so they can be redone.
Usage: python claude_merge.py <batch_he.json>
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = r"C:\tmp\claude_translate.json"
BANKDIR = os.path.join(HERE, "agent_handoff_qa", "retrans_agent_claude")
BANK = os.path.join(BANKDIR, "retrans_corrections.json")
os.makedirs(BANKDIR, exist_ok=True)
FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]'); NIQ = re.compile(r'[֑-ֽֿׁׂ]'); HEB = re.compile(r'[֐-׿]')
STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;'); LOWER = re.compile(r'[a-z]{2,}')
_NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'/]*$"); _CTRL = "".join(chr(c) for c in range(0x20))
def is_namey(en):
    en=(en or "").strip(); ws=en.split()
    return bool(ws) and len(ws)<=4 and all(_NAMEWORD.match(w) for w in ws)
def valid(new, en):
    if not new or not str(new).strip(): return False
    if FOREIGN.search(new) or NIQ.search(new): return False
    if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(en)): return False
    core = STRUCT.sub(" ", en); bare = new.lstrip(_CTRL).strip()
    if LOWER.search(core) and not HEB.search(new):
        if not (bare == en.strip() and is_namey(en)): return False
    return True
src = json.load(open(SRC, encoding="utf-8"))
he = json.load(open(sys.argv[1], encoding="utf-8"))
bank = json.load(open(BANK, encoding="utf-8")) if os.path.exists(BANK) else {}
ok=0; bad=[]
for k, v in he.items():
    en = src.get(k)
    if en is None: bad.append((k,"not-in-src")); continue
    if not isinstance(v, dict): bad.append((k,"not-dict")); continue
    f=(v.get("f") or "").strip(); m=(v.get("m") or "").strip()
    if not f and m: f=m
    if not m and f: m=f
    if valid(f,en) and valid(m,en): bank[k]={"f":f,"m":m}; ok+=1
    else: bad.append((k,"invalid"))
tmp=BANK+".tmp"; json.dump(bank, open(tmp,"w",encoding="utf-8"), ensure_ascii=False); os.replace(tmp,BANK)
print(f"merged {ok} | rejected {len(bad)} | bank total {len(bank)}")
for k,why in bad[:12]: print(f"  REJECT {why}: {k}  EN={src.get(k,'')[:60]!r}")
