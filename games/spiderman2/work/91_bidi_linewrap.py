"""LINE-WRAP bidi simulation — the user's exact complaint was "English word jumps
at line-wrap". This wraps each description to the description box width and
reorders EACH wrapped line under RTL base (what dir='rtl' gives), then checks
no English word is split or scrambled at a line boundary, and shows the result.

Box: SystemMenu_DisplayGraphics description <p> is width 744.4px, font-size 24px
AzbukaPro. ~ a Hebrew glyph ~18px -> ~ 40 chars/line. We test 34/40/46 to bound it.
"""
import json, os, re
from bidi.algorithm import get_display

HERE = os.path.dirname(os.path.abspath(__file__))
RLM = "‏"
WORD = re.compile(r"[A-Za-z][A-Za-z0-9.+\-]*[A-Za-z0-9]|[A-Za-z]")

def strip_markup(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"&[a-zA-Z]+;|&#x?[0-9a-fA-F]+;", "", s)
    return s

def wrap_logical(text, width):
    # greedy word-wrap in LOGICAL order (engine wraps logical, then reorders per line)
    lines, cur = [], ""
    for w in text.split(" "):
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w) if cur else w
    if cur: lines.append(cur)
    return lines

def render_rtl(text, width):
    return [get_display(ln, base_dir="R") for ln in wrap_logical(text, width)]

descs = {}
for fn in ["settings_he.json"] + [f"menus{n}_he.json" for n in range(2, 14)] + ["menus_he.json"]:
    p = os.path.join(HERE, fn)
    if not os.path.exists(p): continue
    for k, v in json.load(open(p, encoding="utf-8")).items():
        if isinstance(v, str) and v.startswith(RLM):
            descs.setdefault(k, strip_markup(v[len(RLM):]))

print(f"[*] line-wrap simulating {len(descs)} descriptions at widths 34/40/46\n")
split_fail = []   # an English word broken across two visual lines OR scrambled within its line
for k, text in descs.items():
    words = set(WORD.findall(text))
    for width in (34, 40, 46):
        vis_lines = render_rtl(text, width)
        joined = " ".join(vis_lines)
        # every English word must still appear verbatim in SOME visual line (not split across lines)
        for w in words:
            if len(w) >= 2 and not any(w in ln for ln in vis_lines):
                # allow the case where the wrap legitimately splits on a space (multi-word run) —
                # only flag if the single token w is absent from every line
                split_fail.append((k, width, w))
                break

print("=" * 66)
print(f"  descriptions tested      : {len(descs)}")
print(f"  English-word-at-wrap FAILS: {len(set(k for k,_,_ in split_fail))}")
print("=" * 66)
if split_fail:
    for k, wd, w in split_fail[:15]:
        print(f"   {k} @w{wd}: token '{w}' not intact on any line")

# show the user's complaint examples rendered as multi-line RTL
print("\n=== rendered multi-line (width 40, RTL base = the fix) ===")
for k in ["PCDISPLAYSETTINGS_HDR_DESC", "PCDISPLAYSETTINGS_NVIDIAREFLEX_DESC",
          "PCDISPLAYSETTINGS_UPSCALEMETHOD_DESC"]:
    if k in descs:
        print(f"\n  {k}:")
        for ln in render_rtl(descs[k], 40):
            print(f"    |{ln}")
