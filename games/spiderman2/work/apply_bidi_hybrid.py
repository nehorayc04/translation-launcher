"""HYBRID bidi fix for the TWO renderers Spider-Man 2 uses:

  * in-game menus  -> cohtml (renders HTML)            -> <span dir='rtl'> works
  * boot launcher + native PC-config dialog -> Win32   -> plain text only
                                                          (HTML tags show literally!)

Many keys (the PC display/graphics settings, the launcher buttons) appear in
BOTH renderers, so they must NOT contain HTML.  Strategy:

  - LAUNCHER_* / PCWARNING_*  (pure Win32)                  -> RLE wrap
  - PCDISPLAYSETTINGS_* / PCGRAPHICSSETTINGS_* / SETTINGSCATEGORY_*
        * a _DESC  (shown only in the in-game description panel) -> <span dir='rtl'>
        * a label/option (shared with the Win32 config dialog)   -> RLE wrap
  - everything else
        * has HTML markup  OR  visible length >= 70 (in-game description) -> <span>
        * otherwise (short in-game label)                                  -> RLE

RLE (U+202B .. U+202C) is a plain Unicode control: invisible in BOTH renderers,
forces RTL, and is enough for single-line strings.  <span dir='rtl'> is only
used where cohtml's HTML bidi is required (multi-line descriptions) and where the
string never reaches the Win32 dialog.

Idempotent: strips any previous span / RLE / isolate / LRM wrap first.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RLE, PDF, LRI, PDI, LRM = "‫", "‬", "⁦", "⁩", "‎"
OPEN, CLOSE = "<span dir='rtl'>", "</span>"

WIN32_PURE = ("LAUNCHER_", "PCWARNING_", "PSPC_")
WIN32_SHARED = ("PCDISPLAYSETTINGS_", "PCGRAPHICSSETTINGS_", "SETTINGSCATEGORY_")

TAGS = re.compile(r"<[^>]+>")
ENTS = re.compile(r"&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;")


def has_heb(s):
    return any("א" <= c <= "ת" for c in s)


def strip_wrap(v):
    v = v.replace(LRI, "").replace(PDI, "").replace(LRM, "")
    while v.startswith(RLE):
        v = v[1:]
    while v.endswith(PDF):
        v = v[:-1]
    while v.startswith(OPEN) and v.endswith(CLOSE):
        v = v[len(OPEN):-len(CLOSE)]
    return v


def visible_len(s):
    return len(ENTS.sub("", TAGS.sub("", s)))


def is_desc(k):
    ku = k.upper()
    return ku.endswith("_DESC") or "_DESC_" in ku or ku.endswith("_BODY") or "_DESC2" in ku


def wrap_for(k, base):
    ku = k.upper()
    if ku.startswith(WIN32_PURE):
        return RLE + base + PDF
    if ku.startswith(WIN32_SHARED):
        return (OPEN + base + CLOSE) if is_desc(k) else (RLE + base + PDF)
    if "<" in base or visible_len(base) >= 70:
        return OPEN + base + CLOSE
    return RLE + base + PDF


FILES = ["settings_he.json", "menus_he.json"] + [f"menus{n}_he.json" for n in range(2, 14)]
total = span = rle = 0
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
        nv = wrap_for(k, base)
        if nv.startswith(OPEN):
            span += 1
        else:
            rle += 1
        if nv != v:
            d[k] = nv
            changed += 1
    if changed:
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"[+] {fn}: {changed}")
        total += changed
print(f"TOTAL changed: {total}  (span={span}, rle={rle})")
