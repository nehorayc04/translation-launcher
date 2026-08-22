"""Wrap every Hebrew-containing menu string with RLE...PDF (U+202B/U+202C) to
force RTL base direction in the game's LTR-base cohtml renderer.

Run only after the RLE approach is confirmed working in-game. Idempotent:
skips values already wrapped. Skips pure-Latin/placeholder/empty values."""
import json, os, glob

HERE = os.path.dirname(os.path.abspath(__file__))
RLE, PDF = "‫", "‬"

def has_heb(s):
    return any("֐" <= c <= "׿" for c in s)

FILES = ["settings_he.json"] + [f"menus{n}_he.json" for n in ([""] + list(range(2, 13)))]
# normalize menus names: menus_he, menus2_he ... menus12_he
FILES = ["settings_he.json", "menus_he.json"] + [f"menus{n}_he.json" for n in range(2, 13)]

total = 0
for fn in FILES:
    p = os.path.join(HERE, fn)
    if not os.path.exists(p):
        continue
    d = json.load(open(p, encoding="utf-8"))
    changed = 0
    for k, v in d.items():
        if not isinstance(v, str) or not v:
            continue
        if v.startswith(RLE):          # already wrapped
            continue
        if not has_heb(v):             # pure latin / placeholder — leave LTR
            continue
        d[k] = RLE + v + PDF
        changed += 1
    if changed:
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"[+] {fn}: wrapped {changed}")
        total += changed
print(f"TOTAL wrapped: {total}")
