"""MSMR probe #6 — READ ONLY. PROVE  enum value == name-table position.

The test (fully self-contained in MSMR, no sibling game needed):

  MSMR ships 12 per-language VOICE archives  a00s0NN.<code>
  MSMR ships 23 per-language TEXT variants, each occupying a span slot
  (span/8 = slot number).

  A language that ships a DUB must also ship SUBTITLES. So under the correct
  mapping, EVERY voice language's enum value must appear in the text-slot set.
  Test both hypotheses and see which one has no orphan.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(r"C:\Users\Nehoray_Cohen\Projects\Game translator")
PROBE = ROOT / "games" / "spiderman_remastered" / "extract" / "loc_variants" / "_probe.json"

NAMES = ["None", "English", "UkEnglish", "Danish", "Dutch", "Finnish", "French",
         "German", "Italian", "Japanese", "Korean", "Norwegian", "Polish",
         "Portuguese", "Russian", "Spanish", "Swedish", "MxSpanish",
         "BrPortuguese", "Arabic", "Turkish", "LaSpanish", "ChineseSimplified",
         "ChineseTraditional", "CaFrench", "Czech", "Hungarian", "Greek",
         "Romanian", "Thai", "Vietnamese", "Indonesian"]

# the 12 shipped voice archives, in toc order, with the language they obviously are
VOICE = [("us", "English"), ("fr", "French"), ("de", "German"), ("it", "Italian"),
         ("jp", "Japanese"), ("pl", "Polish"), ("pt", "Portuguese"), ("ru", "Russian"),
         ("es", "Spanish"), ("br", "BrPortuguese"), ("ar", "Arabic"), ("la", "LaSpanish")]

pj = json.loads(PROBE.read_text(encoding="utf-8"))
vs = pj["variants"]
slots = sorted({v["span"] // 8 for v in vs})
sizes = {v["span"] // 8: v["size"] for v in vs}
print(f"text variants = {len(vs)}   span slots (span/8) = {slots}")
print(f"missing slots in 0..{max(slots)}: {[i for i in range(max(slots)+1) if i not in slots]}")
print(f"\nslot0 size = {sizes.get(0)}   slot1 size = {sizes.get(1)}   identical = {sizes.get(0)==sizes.get(1)}")
print("  (identical slot0/slot1 is what you expect if slot0 == kLanguageNone, a duplicate of English)")

print()
print("=" * 78)
print("HYPOTHESIS TEST — does every DUBBED language have a TEXT slot?")
print("=" * 78)
for label, base in [("H1: enum value == table position  (kLanguageNone = 0)", 0),
                    ("H2: enum value == table position - 1  (kLanguageNone = -1)", 1)]:
    print(f"\n  {label}")
    orphans = []
    print(f"      {'voice':<6} {'language':<16} {'enum value':>10} {'text slot?':>11}")
    for code, lang in VOICE:
        pos = NAMES.index(lang)
        val = pos - base
        ok = val in slots
        if not ok:
            orphans.append((code, lang, val))
        print(f"      .{code:<5} {lang:<16} {val:>10} {'YES' if ok else 'NO  <<< ORPHAN':>11}")
    print(f"      => dubbed-but-no-subtitles orphans: {len(orphans)}  {orphans}")

print()
print("=" * 78)
print("VERDICT")
print("=" * 78)
pos_ar = NAMES.index("Arabic")
print(f"  kLanguageArabic is at name-table position {pos_ar}")
print(f"  H1 -> TextLanguage value for Arabic = {pos_ar}")
print(f"  H2 -> TextLanguage value for Arabic = {pos_ar-1}")
print(f"  LIVE HKCU  Marvel's Spider-Man Remastered\\TextLanguage = 19")
print(f"  LIVE HKCU  Ratchet & Clank - Rift Apart\\TextLanguage    = 1  (R&C pos1 = English)")

print()
print("=" * 78)
print("Full MSMR mapping under H1  (slot present = language ships TEXT)")
print("=" * 78)
for i, n in enumerate(NAMES):
    has = i in slots
    dub = next((c for c, l in VOICE if l == n), None)
    print(f"  {i:>2}  kLanguage{n:<22} text={'YES' if has else '-  '}   dub={'.'+dub if dub else ''}")
print("\nDONE")
