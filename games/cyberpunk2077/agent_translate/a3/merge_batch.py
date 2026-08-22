"""merge_batch.py — validate current_batch_he.json {key:{f,m}} and merge the good ones into the bank.
Anti-cheat: rejects English left on real prose. Rejected keys stay in the slice for a retry."""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.abspath(os.path.join(HERE, "..", "..", "agent_handoff_qa", "retrans_agent_g3", "retrans_corrections.json"))
FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]')
NIQ = re.compile(r'[֑-ֽֿׁׂ]'); HEB = re.compile(r'[֐-׿]')
STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;'); LOWER = re.compile(r'[a-z]{2,}')
NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'/]*$"); CTRL = "".join(chr(c) for c in range(0x20))
def is_namey(en):
    en=(en or "").strip(); ws=en.split()
    return bool(ws) and len(ws)<=4 and all(NAMEWORD.match(w) for w in ws)
def valid(new, en):
    if not new or not str(new).strip(): return False
    if FOREIGN.search(new) or NIQ.search(new): return False
    b = new.lstrip(CTRL).strip()
    if b.startswith("עברית ") or b == "עברית" or "תרגום חלופי" in b: return False   # reject known fabrication-bypass markers
    if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(en)): return False
    core = STRUCT.sub(" ", en); bare = new.lstrip(CTRL).strip()
    if LOWER.search(core) and not HEB.search(new):
        return False   # prose slice: an English passthrough is always wrong -> must be real Hebrew
    if len(en) >= 12 and bare == en.strip() and not is_namey(en): return False
    return True
cb = json.load(open(os.path.join(HERE, "current_batch.json"), encoding="utf-8"))
he = json.load(open(os.path.join(HERE, "current_batch_he.json"), encoding="utf-8"))
bank = json.load(open(BANK, encoding="utf-8")) if os.path.exists(BANK) else {}
ok=0; bad=0; badkeys=[]
for k, en in cb.items():
    v = he.get(k)
    if not isinstance(v, dict): bad+=1; badkeys.append(k); continue
    f=(v.get("f") or "").strip(); m=(v.get("m") or "").strip()
    if not f and m: f=m
    if not m and f: m=f
    if valid(f, en) and valid(m, en): bank[k]={"f":f,"m":m}; ok+=1
    else: bad+=1; badkeys.append(k)
tmp=BANK+".tmp"; json.dump(bank, open(tmp,"w",encoding="utf-8"), ensure_ascii=False); os.replace(tmp, BANK)
for _f in ("current_batch_he.json","current_batch.json"):
    try: os.remove(os.path.join(HERE,_f))
    except OSError: pass
print(f"merged {ok} | rejected {bad} | bank total {len(bank)}")
if badkeys[:8]: print("  rejected sample:", badkeys[:8])
