"""Discriminating 5-method bidi test on visible PC display-setting descriptions.
Each method goes on ONE setting so a single screenshot identifies the winner.
All are BLOCK-level (survive line-wrap), unlike inline <span dir='rtl'>.
Writes overrides into menus13_he.json (loaded last -> wins)."""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RLE, PDF, ALM, RLM = "‫", "‬", "؜", "‏"

def strip(v):
    for c in (RLE, PDF, ALM, RLM, "⁦", "⁩", "‎"):
        v = v.replace(c, "")
    v = v.replace("&rlm;", "")
    v = re.sub(r"<div[^>]*>", "", v).replace("</div>", "")
    v = re.sub(r"<p[^>]*>", "", v).replace("</p>", "")
    v = re.sub(r"<span[^>]*>", "", v).replace("</span>", "")
    return v.strip()

# pull each key's current Hebrew from its source file
SRC = ["settings_he.json"] + [f"menus{n}_he.json" for n in range(2, 13)]
vals = {}
for fn in SRC:
    p = os.path.join(HERE, fn)
    if not os.path.exists(p):
        continue
    d = json.load(open(p, encoding="utf-8"))
    for k, v in d.items():
        if k not in vals and isinstance(v, str) and v:
            vals[k] = strip(v)

def arabicpunct(s):
    return RLM + (s.replace(",", "،").replace("?", "؟").replace(";", "؛"))

# method per key
TESTS = {
    # M1: HTML dir=auto  (first-strong per paragraph)
    "PCDISPLAYSETTINGS_UPSCALEMETHOD_DESC": lambda s: f"<div dir='auto'>{s}</div>",
    # M2: CSS unicode-bidi:plaintext
    "PCDISPLAYSETTINGS_HDR_DESC":           lambda s: f"<div style='unicode-bidi:plaintext;direction:rtl'>{s}</div>",
    # M3: explicit rtl block + right align
    "PCDISPLAYSETTINGS_DLSS_RR_DESC":       lambda s: f"<div dir='rtl' style='text-align:right'>{s}</div>",
    # M4: <p> block rtl (different element)
    "PCDISPLAYSETTINGS_FRAMEGEN_DESC":      lambda s: f"<p dir='rtl'>{s}</p>",
    # M5: Arabic-block punctuation + RLM prefix, NO html (also Win32-safe)
    "PCDISPLAYSETTINGS_VSYNC_DESC":         lambda s: arabicpunct(s),
    # baseline: plain RLE control
    "PCDISPLAYSETTINGS_NVIDIAREFLEX_DESC":  lambda s: RLE + s + PDF,
}

out = {}
for k, fn in TESTS.items():
    if k in vals:
        out[k] = fn(vals[k])
        print(f"[+] {k}: {out[k][:60]}")
    else:
        print(f"[!] MISSING {k}")

json.dump(out, open(os.path.join(HERE, "menus13_he.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print(f"wrote {len(out)} overrides to menus13_he.json")
