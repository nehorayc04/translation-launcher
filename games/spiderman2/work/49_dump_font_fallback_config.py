"""Dump the font-fallback config near the 'hebrew'/'arabic' offsets in
RenoirCore.dll, and the locale->font table in crs-handler.exe."""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")

# --- RenoirCore: dump bytes around hebrew (1700368) and arabic (1727888) ---
print("=== RenoirCore.WindowsDesktop.dll — fallback area around 'hebrew' ===")
d = open(os.path.join(GAME, "RenoirCore.WindowsDesktop.dll"), "rb").read()
# Find all instances of script-name strings
SCRIPTS = [b"hebrew", b"arabic", b"latin", b"cyrillic", b"greek", b"thai",
           b"chinese", b"japanese", b"korean", b"vietnamese", b"devanagari",
           b"bengali", b"armenian", b"georgian", b"georgian", b"khmer",
           b"hangul", b"hiragana", b"katakana", b"han"]
positions = []
for s in SCRIPTS:
    i = 0
    while True:
        j = d.find(s, i)
        if j < 0: break
        positions.append((j, s))
        i = j + 1
positions.sort()
print(f"  found {len(positions)} script-name strings; showing first 30:")
for j, s in positions[:30]:
    start = max(0, j-8)
    end = min(len(d), j+24)
    raw = d[start:end]
    text = ''.join(chr(b) if 0x20<=b<0x7F else '.' for b in raw)
    print(f"  [{j:>8}] {s.decode():<14}  ...{text}...")

# Dump a 256-byte window around 'hebrew' to see the full table
print(f"\n=== 512 bytes around hebrew@1700368 (raw) ===")
chunk = d[1700200:1700800]
# Show as readable: NUL → '.', printable → as is
print(''.join(chr(b) if 0x20<=b<0x7F else ('.' if b==0 else '!') for b in chunk))
print()
print(f"=== 512 bytes around arabic@1727888 (raw) ===")
chunk = d[1727800:1728400]
print(''.join(chr(b) if 0x20<=b<0x7F else ('.' if b==0 else '!') for b in chunk))

# --- crs-handler.exe — locale-to-font table around 'Segoe UI' (807392) ---
print()
print("=== crs-handler.exe — locale table around Segoe UI@807392 ===")
d2 = open(os.path.join(GAME, "crs-handler.exe"), "rb").read()
chunk = d2[807100:808100]
print(''.join(chr(b) if 0x20<=b<0x7F else ('.' if b==0 else '!') for b in chunk))

# --- Look for ALL Segoe references and font sizes in crs-handler ---
print()
print("=== font names + sizes in crs-handler.exe ===")
for needle in (b"Segoe", b"Arial", b"Adobe", b"NotoSans", b"Tahoma",
               b"font", b"Font", b"hebrew", b"arabic"):
    c = d2.count(needle)
    if c:
        j = d2.find(needle)
        start = max(0, j-60)
        end = min(len(d2), j+200)
        raw = d2[start:end]
        text = ''.join(chr(b) if 0x20<=b<0x7F else ('.' if b==0 else '!') for b in raw)
        print(f"  [{j:>8}] {needle.decode('ascii','replace'):<10} x{c}  ...{text}...")
