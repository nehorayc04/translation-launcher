"""FINAL bidi strategy (root-cause CSS fix is applied separately to Shared.css
361465 + 361009 = unicode-bidi:plaintext on the description <p>).

With the container now `unicode-bidi: plaintext`, cohtml derives each
description paragraph's base direction from its first strong char.  So
descriptions must be PLAIN Hebrew (no <span>/<div> wrapper — those trip the
InnerHTMLInlineSpan NBSP quirk I30-73231) with ONE leading U+200F (RLM):
  * RLM forces RTL base even when a description starts with a Latin word.
  * RLM (single mark, not an RLE/PDF pair) can't leave an unbalanced
    embedding if `coh-font-fit-mode:shrink` clips the string.
  * the SAME keys feed the Win32 native config dialog (no CSS) which needs
    a control char for RTL — RLM serves both.

SURGICAL: only DESCRIPTION-type strings (and anything previously wrapped in
<span dir='rtl'>) are converted.  Short LABELS keep their RLE wrap (works in
both the Win32 dialog and cohtml; untouched here)."""
import json, os, re, glob

HERE = os.path.dirname(os.path.abspath(__file__))
RLE, PDF, LRI, PDI, LRM, RLM, ALM = "‫", "‬", "⁦", "⁩", "‎", "‏", "؜"
SPAN_OPEN, SPAN_CLOSE = "<span dir='rtl'>", "</span>"

def has_heb(s):
    return any("א" <= c <= "ת" for c in s)

def strip_wrappers(v):
    for c in (RLE, PDF, LRI, PDI, LRM, RLM, ALM):
        v = v.replace(c, "")
    v = v.replace("&rlm;", "")
    # peel my outer <span dir='rtl'> ... </span> (keep inner <span class='emphasis'> etc.)
    while SPAN_OPEN in v:
        v = v.replace(SPAN_OPEN, "", 1)
        i = v.rfind(SPAN_CLOSE)
        if i != -1:
            v = v[:i] + v[i + len(SPAN_CLOSE):]
    # peel my <div ...>...</div> / <p ...>...</p> block wrappers
    v = re.sub(r"^<div[^>]*>", "", v)
    if v.endswith("</div>"):
        v = v[:-6]
    v = re.sub(r"^<p[^>]*>", "", v)
    if v.endswith("</p>"):
        v = v[:-4]
    # revert the Arabic-punctuation test substitution (menus13 VSYNC test)
    v = v.replace("،", ",").replace("؟", "?").replace("؛", ";")
    return v.strip()

def is_desc(k):
    ku = k.upper()
    return ku.endswith("_DESC") or "_DESC_" in ku or ku.endswith("_BODY") or "_DESC2" in ku

FILES = ["settings_he.json", "menus_he.json"] + [f"menus{n}_he.json" for n in range(2, 14)]
total = conv = 0
for fn in FILES:
    p = os.path.join(HERE, fn)
    if not os.path.exists(p):
        continue
    d = json.load(open(p, encoding="utf-8"))
    changed = 0
    for k, v in list(d.items()):
        if not isinstance(v, str) or not v:
            continue
        had_span = SPAN_OPEN in v
        base = strip_wrappers(v)
        if not has_heb(base):
            continue
        if is_desc(k) or had_span:
            nv = RLM + base                 # plain Hebrew + single RLM
            if nv != v:
                d[k] = nv
                changed += 1
                conv += 1
        # else: leave labels exactly as-is (RLE wrap stays)
    if changed:
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"[+] {fn}: {changed} descriptions -> RLM+plain")
        total += changed
print(f"TOTAL converted: {total}  (descriptions/span-wrapped -> RLM+plain)")
