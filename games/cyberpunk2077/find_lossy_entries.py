"""Compare the in-progress checkpoint to the English source to find
entries where the script ended up keeping the English original
(i.e., values that survived the per-item fallback and got logged as
'single failed, keeping original')."""
import json
import re
from pathlib import Path

CKPT = Path("steam_hebrew_output/steamui/localization/steamui_arabic-json.js.partial.json")
SRC = Path(r"C:\Program Files (x86)\Steam\steamui\localization\steamui_english-json.js")

ckpt = json.loads(CKPT.read_text(encoding="utf-8"))
print(f"checkpoint entries: {len(ckpt):,}")

src_text = SRC.read_text(encoding="utf-8")
m = re.search(r"JSON\.parse\('(.+?)'\)", src_text, re.DOTALL)
raw = m.group(1)

# Reverse js_encode (same logic as steam_translator.js_decode, minimal)
out = []
i = 0
n = len(raw)
while i < n:
    c = raw[i]
    if c == "\\" and i + 1 < n:
        nx = raw[i + 1]
        if nx == "'":   out.append("'");  i += 2
        elif nx == '"': out.append('"');  i += 2
        elif nx == "\\":out.append("\\"); i += 2
        elif nx == "n": out.append("\n"); i += 2
        elif nx == "r": out.append("\r"); i += 2
        elif nx == "t": out.append("\t"); i += 2
        elif nx == "u" and i + 5 < n:
            out.append(chr(int(raw[i + 2:i + 6], 16))); i += 6
        else:
            out.append(nx); i += 2
    else:
        out.append(c); i += 1
src = json.loads("".join(out))
print(f"source keys: {len(src):,}")

heb_re = re.compile(r"[֐-׿]")
lossy = []
for k, v in ckpt.items():
    if k not in src:
        continue
    if v == src[k] and not heb_re.search(v) and re.search(r"[A-Za-z]{3,}", v):
        lossy.append((k, v))

print(f"\nlossy entries (checkpoint value == English source, >=3-letter word, no Hebrew): {len(lossy)}")
for k, v in lossy[:30]:
    print(f"  {k!r}\n    en: {v!r}")
