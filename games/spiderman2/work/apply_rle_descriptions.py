"""Switch every description from a bare RLM prefix (U+200F, a MARK that does NOT
change the paragraph embedding level) to an RLE..PDF embedding
(U+202B .. U+202C) which RAISES the bidi level to RTL for the whole string.

Diagnosis from in-game screenshots: with dir='rtl' (ignored by cohtml) + RLM,
mixed runs still order LEFT-TO-RIGHT (LTR base). cohtml ignores the `dir`
attribute and CSS `direction`, but its ICU engine DOES process Unicode bidi
CONTROL characters in the text stream. RLE is the control that forces RTL base
ordering of the runs, including across soft line-wraps.

Idempotent: strips any prior RLM/RLE/PDF/markup first, then wraps in RLE..PDF.
Only touches description-type values (current RLM-leading, _DESC, or _BODY)."""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RLE, PDF, LRI, PDI, LRM, RLM, ALM = "‫", "‬", "⁦", "⁩", "‎", "‏", "؜"
SPAN_OPEN, SPAN_CLOSE = "<span dir='rtl'>", "</span>"

def has_heb(s): return any("א" <= c <= "ת" for c in s)

def strip_wrappers(v):
    for c in (RLE, PDF, LRI, PDI, LRM, RLM, ALM):
        v = v.replace(c, "")
    v = v.replace("&rlm;", "")
    while SPAN_OPEN in v:
        v = v.replace(SPAN_OPEN, "", 1)
        i = v.rfind(SPAN_CLOSE)
        if i != -1: v = v[:i] + v[i+len(SPAN_CLOSE):]
    v = re.sub(r"^<div[^>]*>", "", v)
    if v.endswith("</div>"): v = v[:-6]
    v = re.sub(r"^<p[^>]*>", "", v)
    if v.endswith("</p>"): v = v[:-4]
    return v.strip()

def is_desc(k):
    ku = k.upper()
    return ku.endswith("_DESC") or "_DESC_" in ku or ku.endswith("_BODY") or "_DESC2" in ku

FILES = ["settings_he.json", "menus_he.json"] + [f"menus{n}_he.json" for n in range(2, 14)]
total = 0
for fn in FILES:
    p = os.path.join(HERE, fn)
    if not os.path.exists(p): continue
    d = json.load(open(p, encoding="utf-8"))
    changed = 0
    for k, v in list(d.items()):
        if not isinstance(v, str) or not v: continue
        # a "description" = we previously RLM-prefixed it, OR it's a *_DESC/_BODY key
        if not (v.startswith(RLM) or is_desc(k)): continue
        base = strip_wrappers(v)
        if not has_heb(base): continue
        nv = RLE + base + PDF
        if nv != v:
            d[k] = nv
            changed += 1
    if changed:
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"[+] {fn}: {changed} -> RLE..PDF")
        total += changed
print(f"TOTAL descriptions re-wrapped to RLE..PDF: {total}")
