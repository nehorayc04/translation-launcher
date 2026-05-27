"""QA on a translated legacy VDF (Steam `resource/*_arabic.txt` style)."""
import re
import sys
from pathlib import Path

REL = sys.argv[1] if len(sys.argv) > 1 else "resource/vgui_arabic.txt"
p = Path("steam_hebrew_output") / REL
raw = p.read_bytes()

# Detect BOM (same logic as steam_translator.translate_vdf)
if raw.startswith(b"\xff\xfe"):
    encoding = "utf-16-le"; body = raw[2:]
elif raw.startswith(b"\xef\xbb\xbf"):
    encoding = "utf-8";     body = raw[3:]
else:
    encoding = "utf-8";     body = raw
text = body.decode(encoding)

print(f"file              : {p}")
print(f"size              : {len(raw):,} bytes")
print(f"encoding          : {encoding}  (BOM: {raw[:3]!r})")

# Language slot check
lang_m = re.search(r'"Language"\s+"([^"]+)"', text)
print(f"Language slot     : {lang_m.group(1) if lang_m else '(missing!)'}")

# Token line stats
kv_re = re.compile(r'^[ \t]*"([^"]+)"[ \t]+"((?:[^"\\]|\\.)*)"', re.MULTILINE)
heb_re = re.compile(r"[֐-׿]")
tokens = kv_re.findall(text)
non_meta = [(k, v) for k, v in tokens if k.lower() != "language" and v.strip()]
with_heb = [(k, v) for k, v in non_meta if heb_re.search(v)]

print(f"token lines       : {len(tokens)}  (excl meta: {len(non_meta)})")
print(f"with Hebrew       : {len(with_heb)}  ({100 * len(with_heb) / max(1, len(non_meta)):.1f}%)")

# Placeholder preservation: count %s / %1$s / {N} occurrences vs source
src = Path(r"C:\Program Files (x86)\Steam") / REL.replace("_arabic.txt", "_english.txt")
if src.exists():
    s_raw = src.read_bytes()
    s_body = s_raw[3:] if s_raw.startswith(b"\xef\xbb\xbf") else (s_raw[2:] if s_raw.startswith(b"\xff\xfe") else s_raw)
    s_enc = "utf-8" if s_raw.startswith(b"\xef\xbb\xbf") or not s_raw.startswith(b"\xff\xfe") else "utf-16-le"
    s_text = s_body.decode(s_enc)
    ph_re = re.compile(r"%[ds]|%\d+\$[ds]|\{\d+\}")
    src_ph = len(ph_re.findall(s_text))
    dst_ph = len(ph_re.findall(text))
    print(f"placeholders src  : {src_ph}")
    print(f"placeholders dst  : {dst_ph}  ({'OK' if dst_ph == src_ph else 'MISMATCH'})")

print("\n--- 8 Hebrew samples ---")
for k, v in with_heb[:8]:
    print(f"  {k!r}: {v!r}")
