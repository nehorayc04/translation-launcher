"""One-shot patch: flip the `"Language" "English"` slot to "Arabic" in the
4 already-translated VDF outputs. The translate_vdf bug skipped this line
because it sits before the "Tokens" block; tokens themselves are fine, so
no re-translation is needed — just this single line per file."""
import re
from pathlib import Path

OUT = Path("steam_hebrew_output")
VDF_FILES = [
    "resource/vgui_arabic.txt",
    "resource/overlay_arabic.txt",
    "resource/platform_arabic.txt",
    "friends/trackerui_arabic.txt",
]

for rel in VDF_FILES:
    p = OUT / rel
    raw = p.read_bytes()
    if raw.startswith(b"\xff\xfe"):
        enc, bom, body = "utf-16-le", b"\xff\xfe", raw[2:]
    elif raw.startswith(b"\xef\xbb\xbf"):
        enc, bom, body = "utf-8", b"\xef\xbb\xbf", raw[3:]
    else:
        enc, bom, body = "utf-8", b"", raw
    text = body.decode(enc)

    # Replace the value of the "Language" key only (first occurrence).
    new_text, n = re.subn(
        r'("Language"[ \t]+")[^"]*(")',
        r'\1Arabic\2',
        text,
        count=1,
    )
    if n == 0:
        print(f"  {rel}: no Language line found (!)")
        continue
    p.write_bytes(bom + new_text.encode(enc))
    m = re.search(r'"Language"[ \t]+"([^"]+)"', new_text)
    print(f"  {rel}: Language -> {m.group(1)!r}")

print("done.")
