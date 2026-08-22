"""Debug merge: simulate exactly what merge_batch.py does for rejected keys"""
import json, re, os
HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.abspath(os.path.join(HERE, "..", "..", "agent_handoff_qa", "retrans_agent_g1", "retrans_corrections.json"))
FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]')
NIQ = re.compile(r'[֑-ֽֿׁׂ]')
STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')
LOWER = re.compile(r'[a-z]{2,}')
NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'/]*$")
CTRL = "".join(chr(c) for c in range(0x20))

def is_namey(en):
    en=(en or "").strip(); ws=en.split()
    return bool(ws) and len(ws)<=4 and all(NAMEWORD.match(w) for w in ws)

def valid(new, en):
    if not new or not str(new).strip(): return False
    if FOREIGN.search(new) or NIQ.search(new): return False
    b = new.lstrip(CTRL).strip()
    if b.startswith("עברית ") or b == "עברית" or "תרגום חלופי" in b: return False
    if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(en)): return False
    core = STRUCT.sub(" ", en); bare = new.lstrip(CTRL).strip()
    if LOWER.search(core) and not HEB.search(new):
        if not (bare == en.strip() and is_namey(en)): return False
    if len(en) >= 12 and bare == en.strip() and not is_namey(en): return False
    return True

HEB = re.compile(r'[֐-׿]')

# Read a previously-written current_batch_he.json that was rejected
he_data = {
    "onscreens/onscreens.json|20139": {"f": "Eva Cole", "m": "Eva Cole"},
    "onscreens/onscreens.json|22030": {"f": "Preset 4", "m": "Preset 4"},
    "onscreens/onscreens.json|27491": {"f": "WNS News", "m": "WNS News"},
    "onscreens/onscreens.json|43811": {"f": "Mat Duda", "m": "Mat Duda"},
    "onscreens/onscreens_final.json|44006": {"f": "Asa Risu", "m": "Asa Risu"},
    "onscreens/onscreens_final.json|49902": {"f": "N54 News", "m": "N54 News"},
    "onscreens/onscreens_final.json|49942": {"f": "Jiro Oba", "m": "Jiro Oba"},
    "onscreens/onscreens_final.json|71918": {"f": "Mary Ann", "m": "Mary Ann"},
}

# These keys must be in the batch that merge_batch reads
# Current batch will have them again. Simulate merge exactly:
tt = json.load(open("to_translate.json", encoding="utf-8"))

for k, v in he_data.items():
    en = tt.get(k, "NOT FOUND")
    f = (v.get("f") or "").strip()
    m = (v.get("m") or "").strip()
    if not f and m: f = m
    if not m and f: m = f
    vf = valid(f, en)
    vm = valid(m, en)
    passed = vf and vm
    print(f"{k}: en={repr(en)}, f={repr(f)}, valid_f={vf}, valid_m={vm}, PASS={passed}")
    if not passed:
        core = STRUCT.sub(" ", en)
        bare = f.strip()
        print(f"  LOWER={bool(LOWER.search(core))}, HEB(f)={bool(HEB.search(f))}")
        print(f"  bare==en.strip(): {repr(bare)} == {repr(en.strip())} -> {bare==en.strip()}")
        print(f"  is_namey(en)={is_namey(en)}")
        print(f"  FOREIGN(f)={bool(FOREIGN.search(f))}, NIQ(f)={bool(NIQ.search(f))}")
        print(f"  STRUCT(f)={sorted(STRUCT.findall(f))}, STRUCT(en)={sorted(STRUCT.findall(en))}")
