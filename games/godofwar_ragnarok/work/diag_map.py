# -*- coding: utf-8 -*-
"""Diagnostic: inject ALL 27 Hebrew codepoints in CONSECUTIVE order into two menu
   slots so the in-game screenshot reveals the exact codepoint->glyph permutation
   the engine applies. Rest of the menu stays Arabic. Uses a lighter font (David)."""
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gowr_wad as W
import gowr_font as F

ROOT = os.path.normpath(os.path.join(HERE, ".."))
SRC  = os.path.join(ROOT, "extract", "r_lang_ar.wad")
LIVE = r'C:\Game Lab\God of War - Ragnarok\exec\wad\pc_le\r_lang_ar.wad'

seq1 = "".join(chr(c) for c in range(0x5d0, 0x5de))   # א..ם  (0x5d0-0x5dd, 14)
seq2 = "".join(chr(c) for c in range(0x5de, 0x5eb))   # מ..ת  (0x5de-0x5ea, 13)
print("seq1:", seq1, "=", " ".join(f"{ord(c):#x}" for c in seq1))
print("seq2:", seq2, "=", " ".join(f"{ord(c):#x}" for c in seq2))

# Base = full hebrew.json (compact -> stays under the Arabic slot -> delta=0 pad),
# then OVERRIDE the two test slots. delta=0 keeps the font intact for a clean test.
base = json.load(open(os.path.join(HERE, "hebrew.json"), encoding="utf-8"))
base["2119"] = seq1
base["2120"] = seq2
over = base

font = r"C:\Windows\Fonts\david.ttf"   # lighter/airier than FRANKB
def inj(blob):
    F.inject_hebrew(blob, font, log=lambda m: print("  [font]", m))

dec, delta = W.pack(over, SRC, LIVE, font_injector=inj)
print(f"deployed (font=David) delta={delta:+}  -> {LIVE}")
print("In-game: New Game slot shows seq1, Continue slot shows seq2.")
print("Read them left-to-right; I'll map each displayed glyph to its input codepoint.")
