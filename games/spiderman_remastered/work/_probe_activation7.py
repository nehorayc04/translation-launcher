"""MSMR probe #7 — READ ONLY. Text/voice independence, first-run seeding, menu depth."""
from __future__ import annotations
import re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GAME = Path(r"D:\Games\Spider-man Remastered")
data = (GAME / "Spider-Man.exe").read_bytes()


def ctx(pat, before=90, after=90, limit=12, enc="ascii"):
    pb = pat.encode(enc)
    out = []
    for m in re.finditer(re.escape(pb), data):
        s, e = max(0, m.start() - before), min(len(data), m.end() + after)
        toks = [t.decode(enc, "replace") for t in re.findall(rb"[\x20-\x7e]{3,}", data[s:e])]
        out.append((m.start(), toks))
        if len(out) >= limit:
            break
    return out


print("=" * 78)
print("1. TextLanguage / AudioLanguage — are they SEPARATE registry values?")
print("=" * 78)
for name in ("TextLanguage", "AudioLanguage"):
    hits = ctx(name, 140, 140, 6)
    print(f"\n  --- {name}  ({len(hits)} occurrence(s) shown) ---")
    for off, toks in hits:
        print(f"      0x{off:08X}: {toks}")

print()
print("=" * 78)
print("2. Registry ROOT path the exe uses")
print("=" * 78)
for pat in ["Insomniac Games", "Software\\Insomniac"]:
    for off, toks in ctx(pat, 120, 160, 6):
        print(f"  0x{off:08X}: {toks}")

print()
print("=" * 78)
print("3. LAUNCHER / first-run / Steam language seeding")
print("=" * 78)
for pat in ["ShowLauncher", "FirstRun", "GetCurrentGameLanguage", "SteamApps",
            "steam_api", "GetAvailableGameLanguages"]:
    n = len(re.findall(re.escape(pat.encode()), data))
    print(f"  {pat:<28} occurrences = {n}")
for off, toks in ctx("GetCurrentGameLanguage", 120, 120, 4):
    print(f"      0x{off:08X}: {toks}")

print()
print("=" * 78)
print("4. Steam-style language NAME table (english/french/arabic/...)")
print("=" * 78)
STEAM = ["english", "french", "german", "italian", "japanese", "koreana", "polish",
         "portuguese", "russian", "spanish", "arabic", "latam", "brazilian",
         "tchinese", "schinese", "turkish", "czech", "hungarian", "greek",
         "romanian", "thai", "vietnamese", "indonesian", "danish", "dutch",
         "finnish", "norwegian", "swedish"]
found = []
for w in STEAM:
    for m in re.finditer(rb"\x00" + w.encode() + rb"\x00", data):
        found.append((m.start(), w))
found.sort()
print(f"  NUL-wrapped steam language names: {len(found)}")
# cluster
cl, cur = [], []
for off, w in found:
    if cur and off - cur[-1][0] > 64:
        if len(cur) >= 5:
            cl.append(cur)
        cur = []
    cur.append((off, w))
if len(cur) >= 5:
    cl.append(cur)
for c in cl:
    print(f"\n   cluster @0x{c[0][0]:08X}  n={len(c)}")
    for off, w in c:
        print(f"      0x{off:08X}  {w}")
if not cl:
    for off, w in found[:40]:
        print(f"      0x{off:08X}  {w}")

print()
print("=" * 78)
print("5. IN-GAME MENU depth for the language control")
print("=" * 78)
for pat in ["SettingsLanguage", "MenuOptionsLanguage", "SettingsSubtitles",
            "MenuOptions", "OPTIONS_LANGUAGE", "LanguageText", "LanguageMask"]:
    n = len(re.findall(re.escape(pat.encode()) + rb"\x00", data))
    print(f"  {pat:<26} NUL-terminated = {n}")
for off, toks in ctx("LanguageText", 120, 120, 6):
    print(f"      0x{off:08X}: {toks}")

print()
print("=" * 78)
print("6. Does the exe read a language from an INI / config file?")
print("=" * 78)
for pat in ["flt.ini", ".ini", "steam_emu", "SteamConfig", "Language="]:
    n = len(re.findall(re.escape(pat.encode()), data))
    print(f"  {pat:<20} occurrences = {n}")

print("\nDONE")
