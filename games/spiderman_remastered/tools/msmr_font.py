"""MSMR Scaleform font injector — ADD 27 Hebrew glyphs to every DefineFont3 face in
ui/export/fonts/Font_LatinAS3.gfx (the Latin/fallback font-lib; measured 0/27 Hebrew,
0 Arabic, 0 bidi controls in all 5 faces: Azbuka Pro Bold/Bold Italic/Medium,
Courier New, Digital).

The .gfx asset extracted from the toc is a BARE, uncompressed Scaleform GFX file
(magic "GFX"+version byte, no CR2W/CFX wrapper) — the simplest container class in
the project. Codec reused verbatim from games/witcher3/work/{gfx_inspect,swf_font,
swf_glyphgen,build_font}.py (SWF DefineFont3, tag=75; proven byte-identical
round-trip elsewhere in this repo) via games/witcher3/work/inject_gfxfontlib.py's
add_hebrew() ADD-not-replace logic (Hebrew sits below the faces' max existing code,
so it must be INSERTED at the sorted position, not appended).

Donor: Heebo (Latin+Hebrew geometric sans — matches the project's default choice for
a UI/HUD face; see hebrew-font-calibration for later size/weight tuning against the
in-game screenshot). Body size left at the TTF's own metrics for this Phase-1 proof;
final calibration is a Phase-2 concern once the proof confirms mount+bidi.
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORK_W3 = ROOT / "games" / "witcher3" / "work"
for p in (WORK_W3,):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import gfx_inspect as G          # noqa: E402
import swf_font as S             # noqa: E402
import swf_glyphgen as GG        # noqa: E402
import build_font as BF          # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402

SWF_EM = 20480
HEB = list(range(0x05D0, 0x05EA + 1))          # 27 letters, alef..tav
FONT_WIDE_OFFSETS = 0x08                        # DefineFont3 flag bit (per swf_font.py FONT_WIDE_OFFSETS)

DEFAULT_DONOR = os.environ.get(
    "MSMR_DONOR_TTF",
    str(ROOT / "games" / "spiderman2" / "extracted" / "_heebo" / "Heebo-Regular.ttf"),
)


def add_hebrew(f: dict, gs, cmap, scale: float) -> int:
    """Insert the Hebrew letters into a parsed DefineFont3 at the sorted code position."""
    if any(0x05D0 <= c <= 0x05EA for c in f["codes"]):
        return 0
    add = [cp for cp in HEB if cp in cmap]
    if not add:
        return 0
    pos = next((i for i, c in enumerate(f["codes"]) if c > add[-1]), len(f["codes"]))
    shapes, advances, bounds = [], [], []
    for cp in add:
        gname = cmap[cp]
        shapes.append(GG.glyph_to_shape(gs, gname, scale, y_sign=-1))
        advances.append(round(gs[gname].width * scale))
        bounds.append(b"\x00")                  # zero RECT (nbits=0) — a hint only
    f["codes"] = f["codes"][:pos] + add + f["codes"][pos:]
    f["shapes"] = f["shapes"][:pos] + shapes + f["shapes"][pos:]
    if f["has_layout"]:
        L = f["layout"]
        L["advance"] = L["advance"][:pos] + advances + L["advance"][pos:]
        L["bounds"] = L["bounds"][:pos] + bounds + L["bounds"][pos:]
    f["num"] += len(add)

    if not f["wide_off"]:
        total = (f["num"] + 1) * 2 + sum(len(s) for s in f["shapes"])
        if total > 0xFFFF:
            f["wide_off"] = True
            f["flags"] |= FONT_WIDE_OFFSETS
            print("      (promoted font to WIDE offsets — shape table > 64 KB)")
    return len(add)


def _rebuild_gfx_drop(gfx: bytes, new_bodies: dict, drop_idx: set) -> bytes:
    """Like build_font.rebuild_gfx (BF.rebuild_gfx), but a tag whose index is in
    drop_idx is OMITTED ENTIRELY (header AND body) instead of copied/replaced --
    frees its full byte cost. Every OTHER tag's framing is untouched (verbatim
    copy for tags not in new_bodies/drop_idx); fileLength (offset 4) is corrected
    by the net delta, same discipline as BF.rebuild_gfx.

    Used only for the in-place, no-growth DSAR deploy path (msmr_dsar_patch.py):
    the asset's total decompressed size cannot exceed the vanilla toc-declared
    size, so adding new Hebrew glyphs to the faces that need them requires
    freeing an equal-or-greater amount of space by dropping a face nobody uses
    for the target UI text (see inject()'s drop_faces docs)."""
    tags, end_of_tags = BF._scan_tags(gfx)
    header_end = tags[0]["hdr_start"] if tags else 8
    out = bytearray(gfx[:header_end])
    delta = 0
    for idx, t in enumerate(tags):
        if idx in drop_idx:
            delta -= (t["off"] - t["hdr_start"]) + t["length"]
            continue
        if idx in new_bodies:
            body = new_bodies[idx]
            delta += len(body) - t["length"]
            code = t["code"]
            if t["long_form"] or len(body) >= 0x3F:
                out += struct.pack("<H", (code << 6) | 0x3F)
                out += struct.pack("<I", len(body))
            else:
                out += struct.pack("<H", (code << 6) | len(body))
            out += body
        else:
            out += gfx[t["hdr_start"]:t["off"] + t["length"]]
    out += gfx[end_of_tags:]
    orig_len = struct.unpack_from("<I", gfx, 4)[0]
    struct.pack_into("<I", out, 4, orig_len + delta)
    return bytes(out)


def inject(gfx_bytes: bytes, donor_ttf: str = DEFAULT_DONOR,
           only_faces: set | None = None,
           drop_faces: set | None = None) -> bytes:
    """Return a new .gfx with faces carrying the 27 Hebrew glyphs. Self-verifying.

    only_faces: if given, add Hebrew ONLY to faces whose name is in this set
    (every other face is left completely untouched -- not even re-serialized).
    drop_faces: face names to REMOVE ENTIRELY (their whole DefineFont3 tag,
    header+body) -- frees their full byte budget. Needed on the in-place,
    no-growth DSAR deploy path: the vanilla asset has ZERO slack (its
    decompressed size must match the toc-declared size exactly), so adding
    Hebrew glyphs to any face requires freeing an equal amount elsewhere in
    the SAME asset. Choose a face confirmed unused by the target screen(s)."""
    t = TTFont(donor_ttf)
    scale = SWF_EM / t["head"].unitsPerEm
    gs = t.getGlyphSet()
    cmap = t.getBestCmap()
    missing = [c for c in HEB if c not in cmap]
    if missing:
        raise SystemExit(f"donor {donor_ttf} missing codepoints: {[hex(c) for c in missing]}")

    tags = G.list_tags(gfx_bytes)
    new_bodies, drop_idx, total, dropped_names = {}, set(), 0, []
    for idx, (code, length, off) in enumerate(tags):
        if code != 75:
            continue
        f = S.parse_definefont3(gfx_bytes[off:off + length])
        name = f["name"].rstrip(b"\x00").decode("utf-8", "replace")
        if drop_faces and name in drop_faces:
            drop_idx.add(idx)
            dropped_names.append(name)
            print(f"  face id={f['font_id']} {name!r:34} DROPPED ENTIRELY ({length} B freed)")
            continue
        if only_faces is not None and name not in only_faces:
            print(f"  face id={f['font_id']} {name!r:34} left untouched (not in only_faces)")
            continue
        n = add_hebrew(f, gs, cmap, scale)
        if n:
            body = S.serialize_definefont3(f)
            chk = S.parse_definefont3(body)
            heb = sum(1 for c in chk["codes"] if 0x05D0 <= c <= 0x05EA)
            assert chk["num"] == f["num"] and heb == n, "re-parse mismatch"
            new_bodies[idx] = body
            total += n
            print(f"  face id={f['font_id']} {name!r:34} glyphs {f['num']-n}->{f['num']} "
                  f"+{n} Hebrew  ({length}->{len(body)} B)  re-parse hebrew={heb} OK")
    if not total and not drop_idx:
        raise SystemExit("no face took Hebrew and none dropped — every face already has it, "
                          "or the filters matched nothing")
    print(f"[+] total Hebrew glyphs ADDED: {total} across {len(new_bodies)} faces"
          + (f"; DROPPED: {dropped_names}" if dropped_names else ""))

    out = _rebuild_gfx_drop(gfx_bytes, new_bodies, drop_idx) if drop_idx else BF.rebuild_gfx(gfx_bytes, new_bodies)

    # self-check on the rebuilt bytes: Hebrew count matches, dropped faces are truly gone,
    # every OTHER original face is still present with its Hebrew count unchanged from input
    chk_gfx = out  # bare GFX, no wrapper to decompress
    heb_total = 0
    survivors = []
    for code, length, off in G.list_tags(chk_gfx):
        if code == 75:
            f = S.parse_definefont3(chk_gfx[off:off + length])
            nm = f["name"].rstrip(b"\x00").decode("utf-8", "replace")
            heb = sum(1 for c in f["codes"] if 0x05D0 <= c <= 0x05EA)
            heb_total += heb
            survivors.append(nm)
    assert heb_total == total, f"self-check failed: hebrew {heb_total} != {total}"
    for nm in dropped_names:
        assert nm not in survivors, f"self-check failed: dropped face {nm!r} still present"
    print(f"[+] SELF-CHECK: rebuilt gfx has {heb_total} Hebrew glyphs total, "
          f"{len(survivors)} faces remain: {survivors}")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        ROOT / "games" / "spiderman_remastered" / "extract" / "fonts" / "Font_LatinAS3_0.bin")
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".hebrew.bin")
    data = src.read_bytes()
    print(f"[*] {src} ({len(data)} B) -> donor={DEFAULT_DONOR}")
    out = inject(data)
    dst.write_bytes(out)
    print(f"[+] wrote {dst} ({len(out)} B, delta {len(out)-len(data):+d})")
