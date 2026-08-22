"""FINAL bidi fix: wrap every Hebrew menu string in <span dir='rtl'>...</span>.

The game's cohtml UI renders localized values as HTML (it already honours
<span class='emphasis'>, <br>, and <span dir='rtl'>).  Setting dir='rtl' makes
cohtml's own HTML bidi engine lay the text out right-to-left WITH correct
per-line reordering, space handling and punctuation placement — which the raw
Unicode control characters (RLE / isolates) could not achieve on this engine.

Strips any previous RLE / PDF / isolate / LRM wrapping first, so it is safe to
re-run.  Leaves pure-Latin / placeholder / empty values untouched.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
RLE, PDF, LRI, PDI, LRM, RLM_C = "‫", "‬", "⁦", "⁩", "‎", "‏"
OPEN, CLOSE = "<span dir='rtl'>", "</span>"


def has_heb(s):
    return any("א" <= c <= "ת" for c in s)


def strip_wrap(v):
    # remove our previous unicode-control wrappers and any prior dir-span
    v = v.replace(LRI, "").replace(PDI, "").replace(LRM, "")
    while v.startswith(RLE):
        v = v[1:]
    while v.endswith(PDF):
        v = v[:-1]
    if v.startswith(OPEN) and v.endswith(CLOSE):
        v = v[len(OPEN):-len(CLOSE)]
    return v


FILES = ["settings_he.json", "menus_he.json"] + [f"menus{n}_he.json" for n in range(2, 14)]

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
        base = strip_wrap(v)
        if not has_heb(base):
            continue
        nv = OPEN + base + CLOSE
        if nv != v:
            d[k] = nv
            changed += 1
    if changed:
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"[+] {fn}: {changed}")
        total += changed
print(f"TOTAL: {total}")
