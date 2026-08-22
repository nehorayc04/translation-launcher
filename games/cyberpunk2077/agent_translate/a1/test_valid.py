import re
STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')
LOWER = re.compile(r'[a-z]{2,}')
HEB = re.compile(r'[֐-׿]')
NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'/]*$")
NIQ = re.compile(r'[֑-ֽֿׁׂ]')
FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]')
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

tests = [
    ("Eva Cole","Eva Cole"),
    ("Preset 4","Preset 4"),
    ("1.315 in","1.315 in"),
    ("WNS News","WNS News"),
    ("Mat Duda","Mat Duda"),
    ("1.315 אינץ'","1.315 in"),
    ("Preset מספר 4","Preset 4"),
    ("WNS News חדשות","WNS News"),
]
for new,en in tests:
    print(f"{en!r} -> new={new!r} valid={valid(new,en)}, is_namey={is_namey(en)}, len_en={len(en)}")
