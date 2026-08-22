"""Does python-bidi apply UBA rule L4 (bracket-glyph mirroring) — i.e. swap the
'(' codepoint to ')' for an RTL-level bracket? Test with a Hebrew-only
parenthetical where there is NO Latin run to anchor the bracket as LTR.
"""
from bidi.algorithm import get_display
A="א"; B="ב"
# Hebrew word, space, '(', Hebrew word, ')'  — all strong-R / neutral
logical = f"{A}{B} ({A}{B})"
got = get_display(logical, base_dir="R")
print("logical :", repr(logical), [hex(ord(c)) for c in logical])
print("visual  :", repr(got), [hex(ord(c)) for c in got])
# Find the bracket codepoints in the output
opens = got.count("(")
closes = got.count(")")
print(f"'(' count {opens}  ')' count {closes}")
# If python-bidi applied L4 mirroring, the visual would have the mirror glyphs
# swapped. If it only reorders, codepoints are preserved but repositioned.
# Determine: in the VISUAL reading R->L, what is the FIRST bracket encountered?
# Reverse the visual to read R->L:
rl = got[::-1]
print("visual read R->L (chars reversed for human eye):", repr(rl))
first_bracket = next((c for c in rl if c in "()"), None)
print("first bracket when reading R->L:", repr(first_bracket),
      "(correct RTL wants '(' first = open-on-right)")
print()
print("INTERPRETATION:")
print(" - If python-bidi LEFT codepoints unmirrored, cohtml must do L4 mirroring")
print("   itself for the parens to look right. cohtml = ICU-based, applies L4.")
print(" - If python-bidi SWAPPED them, the report already shows final glyphs.")
