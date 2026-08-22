"""MSMR activation probe #2 — READ ONLY.

Nails down:
  A. the EXACT kLanguage* enum order in Spider-Man.exe (with file offsets)
  B. any extra language names my first (limit-40) scan truncated
  C. the registry path + value names the exe itself uses
  D. what -userprefs.save actually is (text? binary? does it hold the language?)
  E. TextLanguage=19 -> which language, cross-checked against the 23 loc variants
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GAME = Path(r"D:\Games\Spider-man Remastered")
EXE = GAME / "Spider-Man.exe"
HERE = Path(__file__).resolve().parent
PROBE = HERE.parent / "extract" / "loc_variants" / "_probe.json"
DOCS_MSMR = Path(r"C:\Users\Nehoray_Cohen\Documents\Marvel's Spider-Man Remastered")
DOCS_SM2 = Path(r"C:\Users\Nehoray_Cohen\Documents\Marvel's Spider-Man 2")

data = EXE.read_bytes()
print(f"exe {EXE}  size={len(data):,}")

# ── A. kLanguage* enum, in true binary order ─────────────────
print("\n" + "=" * 76)
print("A. kLanguage* strings in FILE-OFFSET order (NUL-delimited table)")
print("=" * 76)
hits = [(m.start(), m.group().decode()) for m in
        re.finditer(rb"kLanguage[A-Za-z]{0,24}", data)]
# keep only NUL-terminated whole tokens
whole = []
for off, s in hits:
    end = off + len(s)
    if end < len(data) and data[end] == 0:
        whole.append((off, s))
print(f"  raw kLanguage* matches: {len(hits)}   NUL-terminated: {len(whole)}")

# Cluster: consecutive offsets within 64 bytes = one table
clusters, cur = [], []
for off, s in sorted(whole):
    if cur and off - cur[-1][0] > 200:
        clusters.append(cur)
        cur = []
    cur.append((off, s))
if cur:
    clusters.append(cur)
print(f"  clusters: {len(clusters)}")
for ci, cl in enumerate(clusters):
    print(f"\n  --- cluster {ci}  @0x{cl[0][0]:X}..0x{cl[-1][0]:X}  ({len(cl)} entries) ---")
    for i, (off, s) in enumerate(cl):
        print(f"      [{i:2}] 0x{off:08X}  {s}")

# ── B. hunt for language names the limit-40 scan may have cut ─
print("\n" + "=" * 76)
print("B. FULL language-name sweep (any 'k?Language<Name>' + extra scripts)")
print("=" * 76)
extra = ["Chinese", "Traditional", "Simplified", "Thai", "Turkish", "Hungarian",
         "Czech", "Greek", "Hebrew", "Latin", "LatAm", "Mandarin", "Cantonese",
         "Taiwan", "Hant", "Hans"]
for word in extra:
    n = len(re.findall(word.encode("ascii"), data))
    m = len(re.findall(("kLanguage" + word).encode("ascii"), data))
    print(f"  {word:<14} plain={n:<6} kLanguage{word}={m}")

# Every distinct NUL-terminated token starting Language / kLanguage
toks = sorted({m.group().decode() for m in
               re.finditer(rb"(?<![A-Za-z0-9_])k?Language[A-Za-z]{2,24}(?=\x00)", data)})
print(f"\n  distinct Language*/kLanguage* NUL-terminated tokens: {len(toks)}")
for t in toks:
    print("     ", t)

# ── C. registry path + value names ───────────────────────────
print("\n" + "=" * 76)
print("C. REGISTRY strings inside the exe")
print("=" * 76)


def show(pat, enc="ascii", limit=25, width=4):
    pb = pat.encode(enc)
    seen, out = set(), []
    for m in re.finditer(re.escape(pb), data):
        s, e = max(0, m.start() - 100), min(len(data), m.end() + 100)
        rx = rb"[\x20-\x7e]{%d,}" % width if enc == "ascii" else rb"(?:[\x20-\x7e]\x00){%d,}" % width
        for tok in re.findall(rx, data[s:e]):
            t = tok.decode(enc, "replace") if enc == "ascii" else tok.decode("utf-16-le", "replace")
            if pat.lower() in t.lower() and t not in seen:
                seen.add(t)
                out.append((m.start(), t))
                if len(out) >= limit:
                    return out
    return out


for pat in ["Insomniac Games", "SOFTWARE\\", "Software\\", "HKEY", "RegSetValue",
            "RegQueryValue", "RegCreateKey"]:
    r = show(pat)
    print(f"\n  ASCII {pat!r}: {len(r)}")
    for off, t in r[:20]:
        print(f"      0x{off:08X}  {t}")
for pat in ["Insomniac Games", "Marvel's Spider-Man", "Software\\"]:
    r = show(pat, enc="utf-16-le")
    print(f"\n  UTF16 {pat!r}: {len(r)}")
    for off, t in r[:20]:
        print(f"      0x{off:08X}  {t}")

# value names near the enum
print("\n  --- settings value names (exact NUL-terminated) ---")
for name in ["TextLanguage", "AudioLanguage", "TextLanguageIndex", "AudioLanguageIndex",
             "FirstRun", "ShowLauncher", "englishVO", "EnglishVO", "SubtitlesEnabled",
             "TextSubtitlesEnabled", "LanguageMask", "SubtitleTextSize"]:
    n = len(re.findall(re.escape(name.encode()) + rb"\x00", data))
    print(f"      {name:<24} NUL-terminated occurrences = {n}")

# the English-audio setting description
print("\n  --- English-audio override strings ---")
for m in re.finditer(rb"Always use English audio[\x20-\x7e]{0,120}", data):
    print(f"      0x{m.start():08X}  {m.group().decode('ascii','replace')}")
for m in re.finditer(rb"[\x20-\x7e]{0,60}English audio[\x20-\x7e]{0,80}", data):
    print(f"      0x{m.start():08X}  {m.group().decode('ascii','replace')}")

# ── D. -userprefs.save ───────────────────────────────────────
print("\n" + "=" * 76)
print("D. -userprefs.save  (READ ONLY — is it text or a binary blob?)")
print("=" * 76)
for base, label in [(DOCS_MSMR, "MSMR"), (DOCS_SM2, "SM2")]:
    if not base.is_dir():
        continue
    for sub in sorted(base.iterdir()):
        if not sub.is_dir():
            continue
        for f in sorted(sub.glob("*prefs*.save")):
            b = f.read_bytes()
            printable = sum(1 for c in b if 0x20 <= c < 0x7F or c in (9, 10, 13))
            nul = b.count(0)
            strs = [t.decode() for t in re.findall(rb"[\x20-\x7e]{4,}", b)]
            print(f"\n  [{label}] {f.relative_to(base)}   size={len(b)}")
            print(f"      printable={printable}/{len(b)} ({printable*100//max(1,len(b))}%)  NUL={nul}")
            print(f"      first 64 bytes hex: {b[:64].hex()}")
            print(f"      ASCII runs (>=4): {len(strs)}")
            for s in strs[:40]:
                print(f"         {s!r}")
            lang_like = [s for s in strs if re.search(r"lang|Lang|arab|engl|subtit", s, re.I)]
            print(f"      language-ish strings: {lang_like}")

# ── E. loc-variant cross-check ───────────────────────────────
print("\n" + "=" * 76)
print("E. 23 loc variants — script census (which one is the Arabic slot?)")
print("=" * 76)
if PROBE.is_file():
    pj = json.loads(PROBE.read_text(encoding="utf-8"))
    vs = pj.get("variants", [])
    print(f"  variants in _probe.json: {len(vs)}")
    print(f"  {'k':>3} {'span':>5} {'idx':>8} {'size':>10}  scripts(non-ascii>50)")
    for v in vs:
        sc = {k: n for k, n in v["scripts"].items() if n > 50 and k != "ascii"}
        print(f"  {v['k']:>3} {str(v['span']):>5} {v['index']:>8} {v['size']:>10}  {sc}")
else:
    print("  _probe.json missing")

print("\nDONE")
