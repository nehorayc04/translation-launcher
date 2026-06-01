"""Dig inside the largest conduit DAT1 to see if its sections hold compressed
HTML/CSS that references a font (cohtml UI bundle in disguise)."""
import os, sys, io, struct, zlib
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib, dat1lib.types.dat1

R2 = os.path.join(ROOT, "games", "spiderman2", "extracted", "round2")

# Inspect the biggest one — conduit_404227.bin (776 KB)
TARGET = os.path.join(R2, "conduit_404227.bin")
data = open(TARGET, "rb").read()
print(f"[*] {os.path.basename(TARGET)} = {len(data)} bytes")

d = dat1lib.types.dat1.DAT1(io.BytesIO(data), None)
print(f"[*] unk1=0x{d.header.unk1:08X}, sections={len(d.header.sections)}")

for sh in d.header.sections:
    sec = data[sh.offset : sh.offset+sh.size]
    head = sec[:64]
    # Look for printable run, gzip/zlib magic, etc.
    # zlib magic: 0x78 (0x01/0x9C/0xDA), gzip: 1F 8B, zstd: 28 B5 2F FD
    pr = sum(1 for b in head if 0x20<=b<0x7F or b in (0x09, 0x0A, 0x0D))
    is_text = pr > 40
    z_check = sec[:2]
    is_zlib = z_check[0] == 0x78 and z_check[1] in (0x01, 0x9C, 0xDA)
    is_gzip = sec[:2] == b"\x1F\x8B"
    is_zstd = sec[:4] == b"\x28\xB5\x2F\xFD"
    print(f"\n   sec tag=0x{sh.tag:08X}  off={sh.offset:>8}  size={sh.size:>8}  pr={pr}/64  zlib={is_zlib} gzip={is_gzip} zstd={is_zstd}")
    print(f"     head hex: {head[:48].hex(' ')}")
    if is_text:
        # printable text section — dump a chunk
        text_chunk = sec[:600].decode('utf-8', 'replace')
        print(f"     TEXT: {text_chunk[:600]}")
    elif is_zlib or is_gzip:
        try:
            dec = zlib.decompress(sec)
            print(f"     [+] decompressed {len(dec)} bytes  head: {dec[:200]!r}")
        except Exception as e:
            print(f"     decomp error: {e}")
    # Strings hunt — any "font" / "ttf" / "css" / "html" / "noto" in this section?
    for needle in (b"font", b"Font", b".ttf", b".otf", b".css", b".html", b"@font-face",
                   b"Noto", b"noto", b"family", b"sans", b"Arabic", b"Hebrew"):
        c = sec.count(needle)
        if c:
            # show one context
            j = sec.find(needle)
            start = max(0, j-30); end = min(len(sec), j+80)
            ctx = sec[start:end]
            txt = ''.join(chr(b) if 0x20<=b<0x7F else '.' for b in ctx)
            print(f"     hits {needle.decode('ascii','replace'):<12} x{c}  ...{txt}...")

# Also try the .conduit type via the dat1lib autogen — see if it has named sections
print()
print("=== known section types for this asset type ===")
import dat1lib.types.sections as sections_mod
KNOWN = sections_mod.KNOWN_SECTIONS if hasattr(sections_mod, 'KNOWN_SECTIONS') else {}
for sh in d.header.sections:
    cls = KNOWN.get(sh.tag)
    print(f"   tag=0x{sh.tag:08X}  class={cls.__name__ if cls else '(unknown)'}")
