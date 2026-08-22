"""
Master translation loop script.
Reads current_batch.json, produces current_batch_he.json translations,
handling control chars correctly by using the exact en values from the batch.
"""
import json, re, os

STRUCT = re.compile(r"<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;")
LOWER = re.compile(r"[a-z]{2,}")
HEB = re.compile(r"[֐-׿]")
NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'/]*$")
NIQ = re.compile(r"[֑-ֽֿׁׂ]")
FOREIGN = re.compile(r"[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]")
CTRL = "".join(chr(c) for c in range(0x20))

def is_namey(en):
    en_stripped = en.lstrip(CTRL).strip()
    ws = en_stripped.split()
    return bool(ws) and len(ws) <= 4 and all(NAMEWORD.match(w) for w in ws)

def valid(new, en):
    if not new or not str(new).strip(): return False
    if FOREIGN.search(new) or NIQ.search(new): return False
    b = new.lstrip(CTRL).strip()
    if b.startswith("עברית ") or b == "עברית" or "תרגום חלופי" in b: return False
    if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(en)): return False
    core = STRUCT.sub(" ", en)
    bare = new.lstrip(CTRL).strip()
    en_bare = en.lstrip(CTRL).strip()
    if LOWER.search(core) and not HEB.search(new):
        if not (bare == en_bare and is_namey(en)): return False
    if len(en) >= 12 and bare == en_bare and not is_namey(en): return False
    return True

HERE = os.path.dirname(os.path.abspath(__file__))
cb = json.load(open(os.path.join(HERE, "current_batch.json"), encoding="utf-8"))
for k, en in cb.items():
    en_bare = en.lstrip(CTRL).strip()
    ctrl_prefix = en[:len(en) - len(en.lstrip(CTRL))]
    print(f"KEY: {k}")
    print(f"  ctrl_prefix={repr(ctrl_prefix)}, en_bare={repr(en_bare[:60])}")
    print(f"  is_namey={is_namey(en)}, LOWER={bool(LOWER.search(STRUCT.sub(' ', en)))}")
    print(f"  valid(en_bare, en)={valid(en_bare, en)}")
    print()
