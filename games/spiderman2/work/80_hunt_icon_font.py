"""Hunt for the input-prompt / controller icon font across ALL game archives
(not just userinterface). For every asset whose bytes start with an sfnt magic,
parse name + cmap + glyph names, and flag fonts whose glyph names contain
button/mouse/key/dpad/pad/cross/circle/square/triangle/etc OR that carry many
PUA codepoints. Reports idx/asset_id/archive + the icon codepoint->glyphname map."""
import os, sys, io, json, warnings, logging
warnings.filterwarnings("ignore"); logging.disable(logging.CRITICAL)
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib
from fontTools.ttLib import TTFont

MAGICS = (b"\x00\x01\x00\x00", b"OTTO", b"ttcf", b"true")
ICON_KW = ["button","mouse","key","dpad","_pad","cross","circle","square",
           "triangle","prompt","stick","bumper","trigger","_lb","_rb","_lt","_rt",
           "_l1","_r1","_l2","_r2","xbox","gamepad","controller","wheel","scroll",
           "_enter","keycap","hold","slomo","slow"]

with open(os.path.join(GAME, "toc"), "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)
archs = toc.get_archives_section().archives
arch_name = {i: bytes(a.filename).split(b"\x00")[0].decode("ascii","replace")
             for i, a in enumerate(archs)}
ids = toc.get_assets_section().ids

results = []
checked = 0
for idx in range(len(ids)):
    e = toc.get_asset_entry_by_index(idx)
    if not e:
        continue
    if e.size < 2000 or e.size > 30_000_000:
        continue
    try:
        d = bytes(toc.extract_asset(e))
    except Exception:
        continue
    base = None
    for b in (0, 8):
        if d[b:b+4] in MAGICS:
            base = b; break
    if base is None:
        continue
    checked += 1
    try:
        ft = TTFont(io.BytesIO(d[base:]), lazy=True, fontNumber=0)
    except Exception:
        continue
    # glyph names
    try:
        gnames = ft.getGlyphOrder()
    except Exception:
        gnames = []
    iconhits = [g for g in gnames if any(k in g.lower() for k in ICON_KW)]
    # cmap
    cps = set()
    try:
        for t in ft["cmap"].tables:
            try: cps |= set(t.cmap.keys())
            except Exception: pass
    except Exception:
        pass
    pua = sorted(c for c in cps if 0xE000<=c<=0xF8FF or 0xF0000<=c<=0x10FFFD)
    fam = ""
    try: fam = ft["name"].getDebugName(1) or ""
    except Exception: pass
    if iconhits or len(pua) > 20:
        an = arch_name.get(e.archive, "?")
        # codepoint -> glyphname for icon-ish glyphs
        cmap_full = {}
        try:
            cmap_full = ft.getBestCmap()
        except Exception:
            pass
        icon_cps = {hex(c): n for c, n in cmap_full.items()
                    if any(k in n.lower() for k in ICON_KW)}
        results.append({
            "idx": idx, "aid": f"{e.asset_id:016X}", "archive": an,
            "arch_idx": e.archive, "size": e.size, "base": base,
            "family": fam, "nglyphs": len(gnames), "iconhits": len(iconhits),
            "pua": len(pua),
            "sample_iconnames": iconhits[:25],
            "icon_codepoints": dict(list(icon_cps.items())[:40]),
        })
    ft.close()

print(f"[*] checked {checked} sfnt assets; {len(results)} candidate icon fonts\n")
for r in results:
    print(f"idx={r['idx']} aid={r['aid']} arch={r['archive']!r} "
          f"size={r['size']} base={r['base']} fam={r['family']!r} "
          f"glyphs={r['nglyphs']} iconhits={r['iconhits']} PUA={r['pua']}")
    if r["sample_iconnames"]:
        print("   names:", r["sample_iconnames"])
    if r["icon_codepoints"]:
        print("   cps:", r["icon_codepoints"])

out = os.path.join(HERE, "icon_font_hunt.json")
json.dump(results, open(out, "w"), indent=1)
print(f"\n[+] -> {out}")
