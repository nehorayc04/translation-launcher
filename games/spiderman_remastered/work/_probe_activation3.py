"""MSMR activation probe #3 — READ ONLY. The decisive cross-check.

MSMR registry says TextLanguage=19. The exe's kLanguage* table has
kLanguageArabic at TABLE POSITION 19 (counting kLanguageNone as 0).
Ambiguity: does the enum start kLanguageNone=0 (=> 19 is Arabic) or
kLanguageNone=-1 / kLanguageEnglish=0 (=> 19 is Turkish)?

GROUND TRUTH available: Spider-Man 2's TextLanguage=18 is a PROVEN Arabic
(documented in LANG_CONFIGS, live in HKCU right now, Hebrew mod renders).
If SM2's exe carries the same table, the table position of kLanguageArabic
there tells us the offset between table-position and enum-value.

Also: dump the COMPLETE key list of -userprefs.save to prove whether the
language lives in that blob or only in the registry.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CANDIDATE_EXES = [
    (r"Marvel's Spider-Man 2", [
        r"D:\Games\Marvel's Spider-Man 2\Spider-Man2.exe",
        r"C:\Games\Marvel's Spider-Man 2\Spider-Man2.exe",
        r"E:\Games\Marvel's Spider-Man 2\Spider-Man2.exe",
        r"F:\Games\Marvel's Spider-Man 2\Spider-Man2.exe",
        r"D:\Game Lab\Marvel's Spider-Man 2\Spider-Man2.exe",
        r"C:\Game Lab\Marvel's Spider-Man 2\Spider-Man2.exe",
        r"E:\Game Lab\Marvel's Spider-Man 2\Spider-Man2.exe",
        r"F:\Game Lab\Marvel's Spider-Man 2\Spider-Man2.exe",
    ]),
    (r"Ratchet & Clank Rift Apart", [
        r"D:\Games\Ratchet & Clank - Rift Apart\RiftApart.exe",
        r"F:\Game Lab\Ratchet & Clank - Rift Apart\RiftApart.exe",
        r"E:\Games\Ratchet & Clank - Rift Apart\RiftApart.exe",
    ]),
    (r"Miles Morales", [
        r"D:\Games\Marvel's Spider-Man Miles Morales\MilesMorales.exe",
        r"F:\Game Lab\Marvel's Spider-Man Miles Morales\MilesMorales.exe",
    ]),
]

print("=" * 76)
print("SIBLING EXE HUNT (for the enum cross-check)")
print("=" * 76)
found = {}
for label, paths in CANDIDATE_EXES:
    hit = next((p for p in paths if Path(p).is_file()), None)
    print(f"  {label:<30} -> {hit or 'not at any guessed path'}")
    if hit:
        found[label] = Path(hit)

# broaden: scan likely roots one level deep for a *.exe of the right name
if len(found) < 3:
    print("\n  -- widening: scanning game roots --")
    roots = []
    for drv in "CDEFG":
        for r in ("Games", "Game Lab", "SteamLibrary\\steamapps\\common", "Program Files (x86)\\Steam\\steamapps\\common"):
            p = Path(f"{drv}:\\{r}")
            if p.is_dir():
                roots.append(p)
    for r in roots:
        try:
            for d in r.iterdir():
                if not d.is_dir():
                    continue
                if re.search(r"spider|ratchet|rift|miles", d.name, re.I):
                    exes = list(d.glob("*.exe"))
                    big = [e for e in exes if e.stat().st_size > 20_000_000]
                    print(f"      {d}  exes={[e.name for e in exes][:8]}  big={[e.name for e in big]}")
                    for e in big:
                        found.setdefault(d.name, e)
        except OSError as ex:
            print(f"      ({r}: {ex})")


def enum_table(data: bytes):
    hits = []
    for m in re.finditer(rb"kLanguage[A-Za-z]{0,26}", data):
        end = m.end()
        if end < len(data) and data[end] == 0:
            hits.append((m.start(), m.group().decode()))
    hits.sort()
    # cluster
    out, cur = [], []
    for off, s in hits:
        if cur and off - cur[-1][0] > 200:
            out.append(cur); cur = []
        cur.append((off, s))
    if cur:
        out.append(cur)
    return out


print()
print("=" * 76)
print("kLanguage* TABLE per game (table position -> name)")
print("=" * 76)
tables = {}
for label, exe in found.items():
    try:
        d = exe.read_bytes()
    except OSError as e:
        print(f"  {label}: unreadable {e}")
        continue
    cls = enum_table(d)
    if not cls:
        print(f"  {label}: NO kLanguage table ({exe})")
        continue
    big = max(cls, key=len)
    tables[label] = [s for _, s in big]
    print(f"\n  --- {label}  ({exe.name}, {len(d):,} B)  entries={len(big)} ---")
    for i, (off, s) in enumerate(big):
        mark = "   <<<< ARABIC" if s == "kLanguageArabic" else ""
        print(f"      pos {i:2}  0x{off:08X}  {s}{mark}")
    ar = next((i for i, (_, s) in enumerate(big) if s == "kLanguageArabic"), None)
    print(f"      => kLanguageArabic at TABLE POSITION {ar}")

print()
print("=" * 76)
print("CONCLUSION MATRIX")
print("=" * 76)
for label, names in tables.items():
    ar = names.index("kLanguageArabic") if "kLanguageArabic" in names else None
    none0 = names[0] == "kLanguageNone"
    print(f"  {label:<34} table_pos(Arabic)={ar}  starts_with_None={none0}  n={len(names)}")
print("""
  Known ground truth: Spider-Man 2 HKCU TextLanguage=18 == Arabic (proven in-game).
  -> if SM2's table_pos(Arabic)==18 : enum value == table position (None==0)
  -> if SM2's table_pos(Arabic)==19 : enum value == table position - 1 (None==-1)
""")

# ── complete -userprefs.save key list ────────────────────────
print("=" * 76)
print("-userprefs.save : COMPLETE ASCII key list (is the language in there?)")
print("=" * 76)
for base in [Path(r"C:\Users\Nehoray_Cohen\Documents\Marvel's Spider-Man Remastered"),
             Path(r"C:\Users\Nehoray_Cohen\Documents\Marvel's Spider-Man 2")]:
    if not base.is_dir():
        continue
    for sub in sorted(base.iterdir()):
        if not sub.is_dir():
            continue
        for f in sorted(sub.glob("*prefs*.save")):
            b = f.read_bytes()
            strs = [t.decode() for t in re.findall(rb"[\x20-\x7e]{4,}", b)]
            print(f"\n  {base.name} / {f.relative_to(base)}  size={len(b)}  runs={len(strs)}")
            for s in strs:
                print(f"      {s}")
            for probe in ("TextLanguage", "AudioLanguage", "Language", "Arabic", "English"):
                print(f"      contains {probe!r}: {probe.encode() in b}")

print("\nDONE")
