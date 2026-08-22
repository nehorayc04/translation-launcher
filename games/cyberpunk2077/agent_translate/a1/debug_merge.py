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

# Get batch from to_translate directly (simulating what get_batch writes)
tt = json.load(open("to_translate.json", encoding="utf-8"))

rejected_keys = ["onscreens/onscreens.json|20139","onscreens/onscreens.json|22030","onscreens/onscreens.json|27491","onscreens/onscreens.json|43811","onscreens/onscreens_final.json|44006","onscreens/onscreens_final.json|49902","onscreens/onscreens_final.json|49942","onscreens/onscreens_final.json|71918"]

# Simulate what merge_batch does: he maps key -> {f,m}; get en from cb
he_map = {
    "onscreens/onscreens.json|20139": {"f": "Eva Cole", "m": "Eva Cole"},
    "onscreens/onscreens.json|22030": {"f": "Preset 4", "m": "Preset 4"},
    "onscreens/onscreens.json|27491": {"f": "WNS News", "m": "WNS News"},
    "onscreens/onscreens.json|43811": {"f": "Mat Duda", "m": "Mat Duda"},
    "onscreens/onscreens_final.json|44006": {"f": "Asa Risu", "m": "Asa Risu"},
    "onscreens/onscreens_final.json|49902": {"f": "N54 News", "m": "N54 News"},
    "onscreens/onscreens_final.json|49942": {"f": "Jiro Oba", "m": "Jiro Oba"},
    "onscreens/onscreens_final.json|71918": {"f": "Mary Ann", "m": "Mary Ann"},
}

for k in rejected_keys:
    en = tt.get(k, "NOT FOUND")
    v = he_map.get(k)
    if not v:
        print(f"{k}: NO translation"); continue
    f = (v.get("f") or "").strip()
    m = (v.get("m") or "").strip()
    vf = valid(f, en)
    vm = valid(m, en)
    print(f"{k}:")
    print(f"  en={repr(en[:50])}, en_first_byte={hex(ord(en[0])) if en else 'N/A'}")
    print(f"  f={repr(f)}, valid_f={vf}")
    print(f"  m={repr(m)}, valid_m={vm}")
    if not vf:
        core = STRUCT.sub(" ", en)
        bare_f = f.strip()
        print(f"    LOWER(core)={bool(LOWER.search(core))}, HEB(f)={bool(HEB.search(f))}")
        print(f"    bare_f==en.strip()={bare_f==en.strip()}, is_namey(en)={is_namey(en)}")
        en_structs = sorted(STRUCT.findall(en))
        f_structs = sorted(STRUCT.findall(f))
        print(f"    en_structs={en_structs}, f_structs={f_structs}")
    print()
