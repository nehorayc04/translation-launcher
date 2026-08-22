"""Bidi fix for the game's LTR-base cohtml renderer (FINAL method).

For every Hebrew-containing menu string:
  1. strip any previous RLE/PDF wrap,
  2. protect HTML tags + entities (so &rlm; etc. are never mangled),
  3. wrap every Latin/digit run in an LTR isolate (U+2066 .. U+2069) so the
     space around it is preserved and adjacent punctuation stays RTL,
  4. wrap the whole value in RLE .. PDF (U+202B .. U+202C) to force RTL base.

Idempotent: re-strips and re-derives each run, so it can be re-run safely.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RLE, PDF, LRI, PDI = "‫", "‬", "⁦", "⁩"
OBJ = "￼"

PROT = re.compile(r'(?:<[^>]+>)|(?:&[a-zA-Z]+;)|(?:&#\d+;)|(?:&#x[0-9a-fA-F]+;)')
LATRUN = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9 ./®™:_%-]*[A-Za-z0-9])?')


def has_heb(s):
    return any("א" <= c <= "ת" for c in s)


def strip_wrap(v):
    # remove any leading RLE / trailing PDF (possibly several from re-runs)
    while v.startswith(RLE):
        v = v[1:]
    while v.endswith(PDF):
        v = v[:-1]
    # remove any stray isolate chars from a prior run
    return v.replace(LRI, "").replace(PDI, "")


def fix(s):
    saved = []
    def stash(m):
        saved.append(m.group(0))
        return OBJ
    s = PROT.sub(stash, s)
    s = LATRUN.sub(lambda m: LRI + m.group(0) + PDI, s)
    it = iter(saved)
    s = re.sub(OBJ, lambda m: next(it), s)
    return RLE + s + PDF


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
        if not has_heb(base):          # pure latin/placeholder — leave LTR
            continue
        nv = fix(base)
        if nv != v:
            d[k] = nv
            changed += 1
    if changed:
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"[+] {fn}: {changed}")
        total += changed
print(f"TOTAL: {total}")
