# -*- coding: utf-8 -*-
"""DEFINITIVE mapping test: draw LATIN markers into the Hebrew glyph slots
   (0x5d0->'A', 0x5d1->'B', ... 0x5ea->'['), then place known Hebrew words in
   menu slots. Whatever Latin appears reveals the EXACT codepoint->glyph mapping
   with zero font-readability ambiguity."""
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gowr_wad as W
import gowr_font as F

ROOT = os.path.normpath(os.path.join(HERE, ".."))
SRC  = os.path.join(ROOT, "extract", "r_lang_ar.wad")
LIVE = r'C:\Game Lab\God of War - Ragnarok\exec\wad\pc_le\r_lang_ar.wad'

def marker(cp):                      # 0x5d0->'A', 0x5d1->'B', ...
    return chr(ord('A') + (cp - 0x5d0))

# Expected Latin per test word (logical order), so I can decode the screenshot:
def decode(word):
    return "".join(marker(ord(c)) for c in word)

tests = {
    "2119": "אבגדהוזחט",   # consecutive -> expect ABCDEFGHI
    "430":  "הגדרות",       # Settings   -> expect ECDYF[
    "457":  "שלום",         # (Exit slot)-> expect ZMF N
}
for k, w in tests.items():
    print(f"slot {k}: {w!r}  EXPECT Latin (logical) = {decode(w)!r}")

base = json.load(open(os.path.join(HERE, "hebrew.json"), encoding="utf-8"))
base.update(tests)

font = r"C:\Windows\Fonts\arial.ttf"   # crisp Latin markers
def inj(blob):
    F.inject_hebrew(blob, font, render_char=marker, log=lambda m: print("  [font]", m))

dec, delta = W.pack(base, SRC, LIVE, font_injector=inj)
print(f"\ndeployed (LATIN MARKERS) delta={delta:+}  -> {LIVE}")
print("In-game: read the Latin letters in slots New Game / Settings / Exit.")
