"""Input-prompt strings (button glyphs / hold-press labels) box-out in the
list/prompt widgets because the raw RLE/PDF render as tofu there. Strip RLE/PDF
from short prompt strings: any non-description label that contains a bracketed
input token like [ACTION_*], [BTN_*], [L-SHIFT], [C], [2] ... OR is a short
standalone hold/press/tap prompt. Descriptions (_DESC/_BODY) keep their RLE."""
import json, os, re, glob

HERE = os.path.dirname(os.path.abspath(__file__))
RLE, PDF = "‫", "‬"
TOKEN = re.compile(r"\[[A-Z0-9_\-]{1,20}\]")      # [ACTION_DODGE] [L-SHIFT] [C] [2] ...
HOLDWORD = re.compile(r"^(החזק|החזקה|לחץ|הקש|הקלק|לחיצה)\b")
KEEP = ("_DESC", "_DESC2", "_DESC_MKB", "_BODY")

def strip_rle(v):
    while v.startswith(RLE):
        v = v[1:]
    while v.endswith(PDF):
        v = v[:-1]
    return v

def visible(v):
    return re.sub(r"<[^>]+>|\[[^\]]*\]|&[a-zA-Z]+;|[‫‬‏]", "", v)

apply = "--dry" not in os.sys.argv
total = 0
samples = []
for fn in glob.glob(os.path.join(HERE, "menus*_he.json")) + [os.path.join(HERE, "settings_he.json")]:
    d = json.load(open(fn, encoding="utf-8"))
    changed = 0
    for k, v in list(d.items()):
        if not isinstance(v, str) or k.endswith(KEEP):
            continue
        base = strip_rle(v)
        if base == v:                      # nothing to strip
            continue
        is_prompt = bool(TOKEN.search(base)) or (len(visible(base)) <= 12 and HOLDWORD.match(base))
        if not is_prompt:
            continue
        if len(visible(base)) > 60:        # safety: skip long sentences
            continue
        if apply:
            d[k] = base
        if len(samples) < 25:
            samples.append((k, base[:45]))
        changed += 1
    if changed and apply:
        json.dump(d, open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    if changed:
        print(f"[+] {os.path.basename(fn)}: {changed}")
        total += changed
print(f"TOTAL prompt strings stripped: {total}  (apply={apply})")
print("samples:")
for k, s in samples:
    print(f"   {k}: {s}")
