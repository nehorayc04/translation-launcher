"""Find cohtml's font assets: search for .ttf bytes in archives, look inside
the exe's resources, look at d/conduit, list .html/.css/.json assets."""
import os, sys, struct, re
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

# Search dagstr for more UI tokens
DAGSTR = os.path.join(GAME, "dagstr")
data = open(DAGSTR, "rb").read()
print(f"[*] dagstr = {len(data)} bytes")

TOKENS = [b".html", b".htm", b".css", b".cohtml", b".coui",
          b"coui://", b"COUI://", b"cohtml://",
          b".ttf", b".otf", b".woff",
          b"ui/", b"UI/", b"ui\\",
          b"ar-AR", b"ar_AR", b"ar-SA", b"ar_SA",
          b"locale/", b"Locales/", b"i18n/"]

for t in TOKENS:
    c = data.count(t)
    if c:
        print(f"\n  token {t!r:<25} count={c}")
        i = 0; shown = 0
        while shown < 5:
            j = data.find(t, i)
            if j < 0: break
            start = j
            while start > 0 and data[start-1] != 0:
                start -= 1
            end = data.find(b"\x00", j)
            if end < 0: end = j + 200
            s = data[start:end].decode("utf-8", "replace")
            if len(s) < 200:
                print(f"    [{j:>9}] {s!r}")
                shown += 1
            i = end + 1

# Also: look INSIDE the Spider-Man2.exe for ttf signatures and Hebrew font references
print()
print("=== scanning Spider-Man2.exe for embedded font resources ===")
EXE = os.path.join(GAME, "Spider-Man2.exe")
exe = open(EXE, "rb").read()
print(f"  exe = {len(exe)} bytes")

# TTF header magic = 00 01 00 00 (or "OTTO" for CFF)
ttf_hits = [m.start() for m in re.finditer(b"\x00\x01\x00\x00\x00", exe)][:20]
otf_hits = [m.start() for m in re.finditer(b"OTTO", exe)][:20]
print(f"  TTF-like signatures: {len(ttf_hits)} hits  first few: {ttf_hits[:8]}")
print(f"  OTF (OTTO) signatures: {len(otf_hits)} hits  first few: {otf_hits[:8]}")

# Also search for filename strings inside the exe
print()
print("=== fonts/i18n hints inside Spider-Man2.exe ===")
for t in (b".ttf", b".otf", b".woff", b"NotoSans", b"noto_", b"Arabic.ttf",
          b"arabic.ttf", b"freesans", b"FreeSans", b"font", b"FONT_"):
    c = exe.count(t)
    if c:
        print(f"  {t!r:<25}  count={c}")
        i = 0; shown = 0
        while shown < 3:
            j = exe.find(t, i)
            if j < 0: break
            start = max(0, j-40)
            end = min(len(exe), j+80)
            chunk = exe[start:end]
            # show printable parts
            txt = ''.join(chr(b) if 0x20<=b<0x7F else '.' for b in chunk)
            print(f"    [{j:>9}]  ...{txt}...")
            shown += 1
            i = j + 1
