"""The radial quick-select menu ("בחירת קיצור") renders the raw RLE/PDF
(U+202B/U+202C) control chars as visible tofu BOXES (its list-item text widget
does not consume bidi controls, unlike the description widget). Vanilla Arabic
has no RLE there and still renders RTL, so Hebrew will too. Strip RLE/PDF from
the shortcut menu LABEL strings (titles / headers / control prompts) — but NOT
the _DESC descriptions (those live in the description panel that needs RLE)."""
import json, os, re, glob

HERE = os.path.dirname(os.path.abspath(__file__))
RLE, PDF = "‫", "‬"

# keys shown in the radial/quick-select + keybinding rows (labels, not descriptions)
KEEP_RLE_SUFFIX = ("_DESC", "_DESC2", "_DESC_MKB")
TARGET = re.compile(
    r"^(SETTING_SHORTCUT_OPTION_.*_(TITLE|TITLE_MKB|HEADER|CONTROLS|CONTROLS_MKB)"
    r"|MENU_SHORTCUT_HEADER"
    r"|PAUSE_SHORTCUT_\d+_TITLE)$"
)

def strip_rle(v):
    while v.startswith(RLE):
        v = v[1:]
    while v.endswith(PDF):
        v = v[:-1]
    return v

total = 0
for fn in glob.glob(os.path.join(HERE, "menus*_he.json")) + [os.path.join(HERE, "settings_he.json")]:
    d = json.load(open(fn, encoding="utf-8"))
    changed = 0
    for k, v in list(d.items()):
        if not isinstance(v, str):
            continue
        if k.endswith(KEEP_RLE_SUFFIX):
            continue
        if not TARGET.match(k):
            continue
        nv = strip_rle(v)
        if nv != v:
            d[k] = nv
            changed += 1
    if changed:
        json.dump(d, open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"[+] {os.path.basename(fn)}: {changed} shortcut labels stripped of RLE")
        total += changed
print(f"TOTAL shortcut labels -> plain (no RLE box): {total}")
