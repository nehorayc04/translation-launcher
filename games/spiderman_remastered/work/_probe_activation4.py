"""MSMR activation probe #4 — READ ONLY. Pin the enum VALUE (not just table position).

Anchors tried, in order of strength:
  1. Live registry TextLanguage of the SIBLING games whose language we can infer.
  2. The toc's ARCHIVE NAME list: MSMR ships per-language voice archives
     a00s034.<code>. If that code order matches the enum order, it anchors it.
  3. Language 2-letter/locale code tables inside the exe.
  4. The "shipped languages" list (23 loc variants) vs the 32-entry enum.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(r"C:\Users\Nehoray_Cohen\Projects\Game translator")
GAME = Path(r"D:\Games\Spider-man Remastered")
ARCH = GAME / "asset_archive"

# ── 1. registry: every Insomniac game's language values ──────
print("=" * 76)
print("1. LIVE REGISTRY — TextLanguage / AudioLanguage for every Insomniac title")
print("=" * 76)
import winreg

def val(sub, name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub) as k:
            v, t = winreg.QueryValueEx(k, name)
            return v
    except OSError:
        return None

try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Insomniac Games") as k:
        i = 0
        subs = []
        while True:
            try:
                subs.append(winreg.EnumKey(k, i))
            except OSError:
                break
            i += 1
except OSError as e:
    subs = []
    print("  cannot open:", e)

for s in subs:
    full = r"Software\Insomniac Games" + "\\" + s
    print(f"\n  [{s}]")
    for name in ("TextLanguage", "AudioLanguage", "TextLanguageIndex",
                 "AudioLanguageIndex", "englishVO", "EnglishVO", "UseEnglishAudio",
                 "FirstRun", "ShowLauncher", "LanguageMask"):
        v = val(full, name)
        if v is not None:
            print(f"      {name:<20} = {v}")

# ── 2. toc archive names, in table order ─────────────────────
print()
print("=" * 76)
print("2. TOC ARCHIVE LIST (order may mirror the language enum)")
print("=" * 76)
sys.path.insert(0, str(ROOT / "games" / "spiderman2" / "tools" / "ALERT"))
try:
    import dat1lib, dat1lib.types.toc  # noqa
    with open(ARCH / "toc", "rb") as f:
        toc = dat1lib.read(f)
    archs = toc.get_archives_section()
    names = []
    for i, a in enumerate(archs.archives):
        try:
            nm = bytes(a.filename).split(b"\x00")[0].decode("ascii", "ignore")
        except Exception:
            nm = str(a)
        names.append(nm)
        print(f"   [{i:3}] {nm}")
    langsfx = [(i, n) for i, n in enumerate(names) if re.search(r"\.[a-z]{2}$", n)]
    print(f"\n   per-language archives ({len(langsfx)}):")
    for i, n in langsfx:
        print(f"      [{i:3}] {n}   ON DISK={ (ARCH / n).is_file() }")
except Exception as e:
    print("   toc read failed:", e)

# ── 3. locale / 2-letter code tables in the exe ──────────────
print()
print("=" * 76)
print("3. LOCALE-CODE TABLES in Spider-Man.exe")
print("=" * 76)
data = (GAME / "Spider-Man.exe").read_bytes()

# a run of short NUL-terminated 2-5 char lowercase codes near each other
codes = [(m.start(), m.group(1).decode())
         for m in re.finditer(rb"\x00([a-z]{2}(?:[-_][A-Za-z]{2,4})?)\x00", data)]
# cluster them
clusters, cur = [], []
for off, c in codes:
    if cur and off - cur[-1][0] > 48:
        if len(cur) >= 8:
            clusters.append(cur)
        cur = []
    cur.append((off, c))
if len(cur) >= 8:
    clusters.append(cur)
print(f"  code-like clusters (>=8 consecutive): {len(clusters)}")
for cl in clusters[:12]:
    print(f"\n   @0x{cl[0][0]:08X}  n={len(cl)}")
    print("      " + " ".join(c for _, c in cl))

# explicit look for the voice-archive suffix set
SFX = ["us", "uk", "fr", "de", "it", "jp", "kr", "nl", "no", "pl", "pt", "ru",
       "es", "br", "ar", "la", "tr", "cs", "hu", "el", "th", "vi", "id", "da",
       "fi", "sv", "ro", "zh", "ct", "cf"]
print("\n  --- exact NUL-wrapped 2-letter code occurrence counts ---")
row = []
for c in SFX:
    n = len(re.findall(rb"\x00" + c.encode() + rb"\x00", data))
    row.append(f"{c}={n}")
print("      " + "  ".join(row))

# ── 4. numeric anchor: ints adjacent to the enum name table ──
print()
print("=" * 76)
print("4. NUMERIC ANCHOR — bytes around the kLanguage name table")
print("=" * 76)
tbl = 0x04EB3878
print(f"   name table starts 0x{tbl:X}; dumping 0x100 bytes BEFORE it:")
before = data[tbl - 0x100: tbl]
for i in range(0, len(before), 16):
    chunk = before[i:i + 16]
    asc = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in chunk)
    print(f"      0x{tbl-0x100+i:08X}  {chunk.hex(' ')}  |{asc}|")

# pointer table: look for 8-byte LE pointers to the name strings (RVA-ish)
print("\n   Looking for a pointer array referencing the name strings ...")
# compute plausible image base from PE header
import struct
pe_off = struct.unpack_from("<I", data, 0x3C)[0]
opt = pe_off + 24
magic = struct.unpack_from("<H", data, opt)[0]
imgbase = struct.unpack_from("<Q", data, opt + 24)[0] if magic == 0x20B else struct.unpack_from("<I", data, opt + 28)[0]
nsec = struct.unpack_from("<H", data, pe_off + 6)[0]
secoff = opt + struct.unpack_from("<H", data, pe_off + 20)[0]
secs = []
for i in range(nsec):
    o = secoff + i * 40
    nm = data[o:o + 8].rstrip(b"\x00").decode("ascii", "replace")
    vsz, va, rsz, raw = struct.unpack_from("<IIII", data, o + 8)
    secs.append((nm, va, vsz, raw, rsz))
print(f"   image base = 0x{imgbase:X}, sections:")
for nm, va, vsz, raw, rsz in secs:
    print(f"      {nm:<8} VA=0x{va:08X} vsz=0x{vsz:08X} raw=0x{raw:08X} rsz=0x{rsz:08X}")


def off2va(off):
    for nm, va, vsz, raw, rsz in secs:
        if raw <= off < raw + rsz:
            return imgbase + va + (off - raw)
    return None


va_none = off2va(tbl)
print(f"   kLanguageNone file 0x{tbl:X} -> VA 0x{va_none:X}" if va_none else "   (no VA)")
if va_none:
    ptr = struct.pack("<Q", va_none)
    refs = [m.start() for m in re.finditer(re.escape(ptr), data)]
    print(f"   pointers to kLanguageNone: {len(refs)} -> {[hex(r) for r in refs[:6]]}")
    for r in refs[:3]:
        print(f"\n   --- pointer array @0x{r:08X} (16 qwords) ---")
        for j in range(16):
            q = struct.unpack_from("<Q", data, r + j * 8)[0]
            # resolve back
            tgt = None
            for nm, va, vsz, raw, rsz in secs:
                if imgbase + va <= q < imgbase + va + vsz:
                    fo = raw + (q - imgbase - va)
                    if 0 <= fo < len(data):
                        s = data[fo:fo + 40].split(b"\x00")[0]
                        try:
                            tgt = s.decode("ascii")
                        except Exception:
                            tgt = None
                    break
            print(f"      [{j:2}] 0x{q:016X}  {tgt}")

print("\nDONE")
