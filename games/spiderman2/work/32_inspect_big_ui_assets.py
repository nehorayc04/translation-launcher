"""Look INSIDE the two biggest UI assets (23 MB & 17.9 MB) — they might contain
the font as part of a packed cohtml resource bundle."""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
OUT  = os.path.join(ROOT, "games", "spiderman2", "extracted", "ui_big_assets")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)

TOP = [422626, 15610, 298871, 396876]   # top-4 UI assets

KNOWN = {b"CFF ", b"CFF2", b"head", b"hhea", b"maxp", b"name", b"post",
         b"OS/2", b"cmap", b"glyf", b"loca", b"GPOS", b"GSUB", b"hmtx",
         b"vmtx", b"vhea", b"DSIG", b"BASE", b"GDEF"}

def validate(buf, j, magic):
    if buf[j:j+4] != magic: return None
    nt = struct.unpack(">H", buf[j+4:j+6])[0]
    if not (4 <= nt <= 40): return None
    if j+12 + nt*16 > len(buf): return None
    extents = []
    known = 0
    for k in range(nt):
        rec = buf[j+12 + k*16 : j+12 + (k+1)*16]
        tag = rec[:4]
        if not all(0x20<=b<=0x7E for b in tag): return None
        off = struct.unpack(">I", rec[8:12])[0]
        ln = struct.unpack(">I", rec[12:16])[0]
        extents.append((tag, off, ln))
        if tag in KNOWN: known += 1
    if known < 5: return None
    total = max(o+l for _, o, l in extents)
    if total > len(buf) - j: return None
    return total

aid_section = toc.get_assets_section()
for target_idx in TOP:
    # Find entry
    e = None
    for idx in range(len(aid_section.ids)):
        ee = toc.get_asset_entry_by_index(idx)
        if ee is not None and ee.index == target_idx:
            e = ee
            break
    if not e:
        print(f"[!] not found: {target_idx}")
        continue
    try:
        d = bytes(toc.extract_asset(e))[36:]
    except Exception as ex:
        print(f"[!] extract failed for {target_idx}: {ex}")
        continue

    outp = os.path.join(OUT, f"ui_{target_idx}.bin")
    with open(outp, "wb") as wf: wf.write(d)
    print(f"\n=== idx={target_idx}  size={len(d)}  saved to {os.path.basename(outp)} ===")
    print(f"  head 32 bytes: {d[:32].hex(' ')}")
    print(f"  head as ASCII:  {d[:32].decode('ascii', 'replace')}")
    # Look for embedded fonts
    fonts_in = 0
    for magic in (b"OTTO", b"\x00\x01\x00\x00", b"ttcf"):
        i = 0
        while True:
            j = d.find(magic, i)
            if j < 0: break
            total = validate(d, j, magic)
            if total and 20_000 < total < 50_000_000:
                fonts_in += 1
                print(f"   FONT inside! magic={magic!r} off={j} total={total}")
                # save it
                with open(os.path.join(OUT, f"ui_{target_idx}_font_off{j}.bin"), "wb") as wf:
                    wf.write(d[j:j+total])
            i = j + 4
    print(f"   fonts found: {fonts_in}")
    # Probe strings
    for needle in (b"font-family", b"@font-face", b"NotoSans", b"Noto", b"Arabic",
                   b"arabic", b"hebrew", b"Hebrew", b".ttf", b".otf",
                   b".woff", b".woff2", b"coui://", b"const ", b"function "):
        c = d.count(needle)
        if c > 0:
            # show first context
            j = d.find(needle)
            start = max(0, j-30); end = min(len(d), j+100)
            ctx = d[start:end]
            txt = ''.join(chr(b) if 0x20<=b<0x7F else '.' for b in ctx)
            print(f"   '{needle.decode('ascii','replace')}' x{c}  ctx: ...{txt}...")
