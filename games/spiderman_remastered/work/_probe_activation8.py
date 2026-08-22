"""MSMR probe #8 — READ ONLY. CONTROLS for every negative claim."""
from __future__ import annotations
import re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MSMR = Path(r"D:\Games\Spider-man Remastered\Spider-Man.exe").read_bytes()
RC = Path(r"F:\Game Lab\Ratchet & Clank - Rift Apart\RiftApart.exe").read_bytes()

print("=" * 78)
print("CONTROLS — every negative must be paired with a known-positive")
print("=" * 78)
print(f"  MSMR exe {len(MSMR):,} B      R&C exe {len(RC):,} B\n")

def n(buf, s):
    return len(re.findall(re.escape(s.encode()), buf))

rows = [
    # (string,                     why it matters)
    ("TextLanguage",     "POSITIVE control - must be >0 in both"),
    ("kLanguageArabic",  "POSITIVE control - must be >0 in both"),
    ("ShowLauncher",     "MSMR claim: NO Nixxes launcher. R&C = control (its HKCU has ShowLauncher=1)"),
    ("englishVO",        "SM2 uses this reg value; is it in MSMR/R&C?"),
    ("UseEnglishAudio",  "MSMR's audio override (lives in -userprefs.save)"),
    ("AudioLanguage",    "text/voice independence"),
    ("flt.ini",          "MSMR claim: game never reads flt.ini"),
    (".ini",             "MSMR claim: game reads no .ini at all"),
    ("Language=",        "MSMR claim: no INI-style language key"),
    ("kLanguageHebrew",  "claim: NO Hebrew locale anywhere"),
    ("kLanguageMxSpanish","MSMR has it, R&C does not (enum differs per title)"),
    ("kLanguageCroatian","R&C has it, MSMR does not"),
]
print(f"  {'string':<22} {'MSMR':>8} {'R&C':>8}   note")
for s, why in rows:
    print(f"  {s:<22} {n(MSMR,s):>8} {n(RC,s):>8}   {why}")

print()
print("=" * 78)
print("UTF-16 control (a negative in ASCII must also be checked in UTF-16)")
print("=" * 78)
for s in ("flt.ini", ".ini", "Language=", "Hebrew", "TextLanguage"):
    a = n(MSMR, s)
    u = len(re.findall(re.escape(s.encode("utf-16-le")), MSMR))
    print(f"  {s:<16} ascii={a:<6} utf16={u}")

print()
print("=" * 78)
print("REGISTRY PATH string — exact, both encodings")
print("=" * 78)
for s in [r"Software\Insomniac Games\Marvel's Spider-Man Remastered",
          r"Software\Insomniac Games"]:
    print(f"  ascii {n(MSMR,s):>3}   utf16 {len(re.findall(re.escape(s.encode('utf-16-le')), MSMR)):>3}   {s}")

print("\nDONE")
