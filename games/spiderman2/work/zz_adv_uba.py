"""Validate python-bidi == UBA on textbook cases, and confirm the report's
rtl_visual matches a fresh re-derivation (no generation bug)."""
import json, os, re
from bidi.algorithm import get_display
HERE=os.path.dirname(os.path.abspath(__file__))
RLM="‏"

# --- textbook UBA cases (from the Unicode bidi reference) ---
# Hebrew letters use uppercase A-D placeholder convention? No - use real chars.
A="א"; B="ב"; G="ג"  # strong R
def R(s): return get_display(s, base_dir="R")

cases = [
    # (logical, expected RTL visual, note)
    (f"{A}{B}{G} 123", "123 גבא", "Hebrew word then number: number stays LTR, word reversed, number on left"),
    (f"car {A}{B}{G}", "גבא car", "L-run 'car' then Hebrew: in RTL base, Hebrew on right, car on left, car NOT reversed"),
    (f"{A}{B} (test)", "(test) בא", "parenthesized latin inside RTL — brackets mirrored so '(' stays opening"),
    (f"{A}{B} 5%", "5% בא", "percent with number"),
    ("100x", "100x", "pure latin/number stays as-is"),
]
print("=== UBA textbook conformance (python-bidi 0.6.10) ===")
allok=True
for logical, expected, note in cases:
    got=R(logical)
    ok = got==expected
    allok &= ok
    print(f"  [{'OK' if ok else 'FAIL'}] {logical!r:20} -> {got!r:18} exp {expected!r:18}  {note}")
print(f"  ALL TEXTBOOK OK: {allok}")

# --- bracket mirroring check (critical: cohtml/UBA mirrors () [] at render) ---
print("\n=== bracket mirroring (logical '(' should render as visual ')' at the swapped edge) ===")
for logical in [f"{A}{B} (x)", f"{A}{B} [y]"]:
    print(f"  {logical!r} -> {R(logical)!r}")

# --- confirm report rtl_visual == fresh re-derivation for 200 random rows ---
def strip(s):
    s=re.sub(r"<[^>]+>","",s); s=re.sub(r"&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;","",s); return s
def vis(s,b): return "\n".join(get_display(p,base_dir=b) for p in re.split(r"[\n\r]",s))

rep=json.load(open(os.path.join(HERE,"bidi_sim_report.json"),encoding="utf-8"))
# rebuild source map
src={}
for fn in ["settings_he.json"]+[f"menus{n}_he.json" for n in range(2,14)]+["menus_he.json"]:
    p=os.path.join(HERE,fn)
    if not os.path.exists(p): continue
    for k,v in json.load(open(p,encoding="utf-8")).items():
        if isinstance(v,str): src.setdefault(k,v)

mismatch=0; checked=0
for r in rep:
    k=r["key"]; raw=src.get(k)
    if not raw or not raw.startswith(RLM): continue
    t=strip(raw[len(RLM):])
    fresh=vis(RLM+t,"R").replace(RLM,"")[:120]
    checked+=1
    if fresh != r["rtl_visual"]:
        mismatch+=1
        if mismatch<=5:
            print(f"  MISMATCH {k}:\n    report: {r['rtl_visual'][:80]!r}\n    fresh : {fresh[:80]!r}")
print(f"\n=== report fidelity: {checked} checked, {mismatch} mismatches vs fresh re-derivation ===")
