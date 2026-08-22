#!/usr/bin/env python3
"""
Shared map for the Arabic-slot Hebrew font-hijack.

The engine, in Arabic (ar-SA) mode, routes Arabic-script codepoints to its Arabic
font and applies the engine's own RTL bidi + Arabic shaping. Hebrew-script codepoints
are routed elsewhere (a font without Hebrew) -> tofu. So to get Hebrew glyphs to appear
through the Arabic RTL path, we:

  1. TRANSLITERATE each Hebrew codepoint (U+05D0..05EA) to a distinct ARABIC carrier
     codepoint (U+06xx) in the stored text  -> the engine treats the run as Arabic
     (strong RTL) and routes it to the Arabic font.
  2. PATCH the (loose) AvenirNextWorld fonts so cmap[carrier] points at the font's
     EXISTING Hebrew glyph. Because the Arabic GSUB shaping lookups key off the ORIGINAL
     Arabic glyph ids (not the Hebrew ones we now map to), no positional substitution or
     ligature fires on the carriers -> the plain Hebrew glyph renders, in RTL order.

Result: real engine bidi (right-aligned, correct order), Hebrew glyphs, no manual
reversal. Non-space/Latin/digit characters are left unchanged (they render normally).

27 Hebrew letters (incl. the 5 final forms) -> 27 distinct Arabic letter codepoints.
"""

# Hebrew block U+05D0..U+05EA in order (22 base + 5 final forms interspersed = 27)
_HEB = list(range(0x05D0, 0x05EB))

# 27 Arabic letter codepoints used purely as carriers (all present in AvenirNextWorld).
# Order is arbitrary; the only requirement is a stable 1:1 mapping.
_CARRIERS = [
    0x0627, 0x0628, 0x062A, 0x062B, 0x062C, 0x062D, 0x062E, 0x062F, 0x0630,
    0x0631, 0x0632, 0x0633, 0x0634, 0x0635, 0x0636, 0x0637, 0x0638, 0x0639,
    0x063A, 0x0641, 0x0642, 0x0643, 0x0644, 0x0645, 0x0646, 0x0647, 0x0648,
]
assert len(_HEB) == len(_CARRIERS) == 27

HEB_TO_CARRIER = {h: c for h, c in zip(_HEB, _CARRIERS)}
CARRIER_TO_HEB = {c: h for h, c in HEB_TO_CARRIER.items()}


def translit(text):
    """Hebrew codepoints -> Arabic carrier codepoints; everything else unchanged."""
    return "".join(chr(HEB_TO_CARRIER.get(ord(ch), ord(ch))) for ch in text)


if __name__ == "__main__":
    for h, c in HEB_TO_CARRIER.items():
        print(f"U+{h:04X} {chr(h)}  ->  U+{c:04X} {chr(c)}")
