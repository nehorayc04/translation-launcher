"""MSMR probe #5 — READ ONLY. Pin the enum value with the adjacent locale-code table."""
from __future__ import annotations
import re, struct, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GAME = Path(r"D:\Games\Spider-man Remastered")
data = (GAME / "Spider-Man.exe").read_bytes()

TBL = 0x04EB3878           # kLanguageNone
print("=" * 76)
print("RAW DUMP: enum-name table + everything after it (0x04EB3878 .. +0x340)")
print("=" * 76)
seg = data[TBL: TBL + 0x340]
for i in range(0, len(seg), 16):
    ch = seg[i:i + 16]
    asc = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in ch)
    print(f"  0x{TBL+i:08X}  {ch.hex(' ')}  |{asc}|")

print()
print("=" * 76)
print("NUL-separated token stream from 0x04EB3878 (name table then code table)")
print("=" * 76)
toks, off = [], TBL
end = TBL + 0x340
while off < end:
    nxt = data.find(b"\x00", off)
    if nxt < 0 or nxt > end:
        break
    s = data[off:nxt]
    if s:
        toks.append((off, s.decode("ascii", "replace")))
    off = nxt + 1
for i, (o, t) in enumerate(toks):
    print(f"  [{i:3}] 0x{o:08X}  {t!r}")

# ── align names vs codes ──
names = [t for _, t in toks if t.startswith("kLanguage")]
codes = [t for _, t in toks if re.fullmatch(r"[a-z]{2}", t)]
print()
print("=" * 76)
print(f"ALIGNMENT   names={len(names)}  codes={len(codes)}")
print("=" * 76)
print(f"  {'pos':>4} {'kLanguage name':<30} {'code':<6}")
for i, n in enumerate(names):
    # names[0] is kLanguageNone which has no locale code -> codes[i-1]
    c = codes[i - 1] if 0 < i <= len(codes) else ""
    mark = "  <<<< ARABIC" if n == "kLanguageArabic" else ""
    print(f"  {i:>4} {n:<30} {c:<6}{mark}")

print("""
  If code[j] pairs with name[j+1] (None has no locale code), then
  kLanguageEnglish == 'us' and the enum VALUE == table position.
""")

# ── SM2 exe hunt via Saved Games shortcuts ──
print("=" * 76)
print("SM2 EXE HUNT — resolve the .lnk shortcuts in Saved Games")
print("=" * 76)
sg = Path(r"C:\Users\Nehoray_Cohen\Saved Games")
for lnk in sorted(sg.glob("*.lnk")):
    b = lnk.read_bytes()
    # crude: pull printable paths out of the lnk
    a = set(t.decode() for t in re.findall(rb"[\x20-\x7e]{6,}", b) if b":\\" in t or b"\\" in t)
    u = set(t.decode("utf-16-le", "replace") for t in re.findall(rb"(?:[\x20-\x7e]\x00){6,}", b))
    cands = sorted({s for s in (a | u) if re.search(r"[A-Za-z]:\\|\\\\", s)})
    print(f"\n  {lnk.name}")
    for c in cands[:12]:
        print(f"      {c}")

# ── broad but bounded exe hunt ──
print()
print("=" * 76)
print("BROAD HUNT for Spider-Man2.exe / Overstrike / Mods Library")
print("=" * 76)
targets = re.compile(r"^(Spider-?Man2?\.exe|Overstrike\.exe)$", re.I)
roots = []
for drv in "CDEFG":
    d = Path(f"{drv}:\\")
    if d.exists():
        roots.append(d)
for r in roots:
    try:
        for lvl1 in r.iterdir():
            if not lvl1.is_dir():
                continue
            if lvl1.name.lower() in ("windows", "$recycle.bin", "system volume information",
                                     "programdata", "perflogs"):
                continue
            try:
                for lvl2 in lvl1.iterdir():
                    if not lvl2.is_dir():
                        continue
                    if not re.search(r"spider|insomniac|marvel|overstrike", lvl2.name, re.I):
                        continue
                    print(f"  DIR {lvl2}")
                    try:
                        for f in lvl2.iterdir():
                            if f.is_file() and f.suffix.lower() == ".exe":
                                print(f"        {f.stat().st_size:>12}  {f.name}")
                    except OSError:
                        pass
            except OSError:
                pass
    except OSError as e:
        print(f"  ({r}: {e})")

print("\nDONE")
