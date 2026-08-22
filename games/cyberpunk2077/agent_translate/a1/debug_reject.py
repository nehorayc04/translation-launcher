import json, re
STRUCT = re.compile(r"<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;")
LOWER = re.compile(r"[a-z]{2,}")
HEB = re.compile(r"[֐-׿]")
NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'/]*$")
NIQ = re.compile(r"[֑-ֽֿׁׂ]")
FOREIGN = re.compile(r"[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]")
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

rejected = ["onscreens/onscreens.json|20139","onscreens/onscreens.json|22030","onscreens/onscreens.json|27491","onscreens/onscreens.json|43811","onscreens/onscreens_final.json|44006","onscreens/onscreens_final.json|49902","onscreens/onscreens_final.json|49942","onscreens/onscreens_final.json|71918"]

tt = json.load(open("to_translate.json", encoding="utf-8"))
for k in rejected:
    en = tt.get(k, "NOT FOUND")
    en_raw_chars = [hex(ord(c)) for c in en[:10]] if en else []
    print(f"KEY: {k}")
    print(f"  EN repr: {repr(en[:80])}")
    print(f"  EN first 10 chars: {en_raw_chars}")
    print(f"  is_namey(en)={is_namey(en)}, LOWER={bool(LOWER.search(STRUCT.sub(' ',en)))}")
    print(f"  valid(en,en)={valid(en,en)}")
    print()
