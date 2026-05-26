"""Quick QA on the translated Steam bundle."""
import json
import re
from pathlib import Path

p = Path("steam_hebrew_output/steamui/localization/steampops_arabic-json.js")
text = p.read_text(encoding="utf-8")
m = re.search(r"JSON\.parse\('(.+?)'\)", text, re.DOTALL)
assert m, "no JSON.parse wrapper found"
raw = m.group(1)

# Reverse js_encode: \\ -> \  and  \' -> '  and  \n \r \t  and  \uXXXX
out = []
i = 0
n = len(raw)
while i < n:
    c = raw[i]
    if c == "\\" and i + 1 < n:
        nxt = raw[i + 1]
        if nxt == "'":   out.append("'");  i += 2
        elif nxt == '"': out.append('"');  i += 2
        elif nxt == "\\":out.append("\\"); i += 2
        elif nxt == "n": out.append("\n"); i += 2
        elif nxt == "r": out.append("\r"); i += 2
        elif nxt == "t": out.append("\t"); i += 2
        elif nxt == "u" and i + 5 < n:
            out.append(chr(int(raw[i + 2:i + 6], 16))); i += 6
        else:
            out.append(nxt); i += 2
    else:
        out.append(c); i += 1

payload = "".join(out)
data = json.loads(payload)
print(f"total keys           : {len(data)}")
print(f"language slot        : {data.get('language')!r}")

heb_re = re.compile(r"[֐-׿]")
heb_keys = [k for k, v in data.items() if isinstance(v, str) and heb_re.search(v)]
print(f"keys with Hebrew     : {len(heb_keys)}")

# Untranslated alphabetic strings (excluding 'language' meta)
still_eng = [
    (k, v) for k, v in data.items()
    if k != "language"
    and isinstance(v, str)
    and v.strip()
    and re.search(r"[A-Za-z]{3,}", v)
    and not heb_re.search(v)
]
print(f"still-English (3+ alpha): {len(still_eng)}")

print("\n--- 6 Hebrew samples ---")
for k in heb_keys[:6]:
    print(f"  {k!r}: {data[k]!r}")

print("\n--- 6 still-English samples (likely intentional brand/placeholder) ---")
for k, v in still_eng[:6]:
    print(f"  {k!r}: {v!r}")

print(f"\nfile size: {p.stat().st_size:,} bytes")
