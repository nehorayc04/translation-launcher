"""Inject Hebrew glyphs (U+05D0..U+05EA + punctuation) into Skyrim SE Scaleform fonts.

Skyrim's UI fonts are REAL SWF DefineFont3 tags inside interface/fonts_*.swf.
We EXTEND a face: add new (code, shape, advance, bounds) entries keeping the code
table ASCENDING (Scaleform binary-searches it), then re-serialize.

Three structures move together and MUST stay in lockstep (num entries each):
    codes[]  shapes[]  layout.advance[]  layout.bounds[]
plus the sibling DefineFontAlignZones tag (73) which carries ONE 10-byte ZoneRecord
per glyph -- we append neutral zero-zones so its count still matches.

Guards:
  * offsets are u16 unless FONT_WIDE_OFFSETS; if the extended table would overflow
    0xFFFF we PROMOTE the font to wide offsets (flag 0x08) instead of corrupting it.
  * codes are re-sorted, so a Hebrew block lands mid-table (above Latin, below U+2122).
  * every rebuilt tag is re-parsed and validated before it is written back.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parents[1] / "007_first_light" / "tools"))

import swf as SWF                                        # noqa: E402
from swf_font import parse_definefont3, serialize_definefont3   # noqa: E402
from swf_glyphgen import BitWriter, ContourPen, _sbits          # noqa: E402
from shape import shape_bbox, measure_face                      # noqa: E402

# MEASURED from the shipped fonts (games/skyrim/tools/shape.py):
#   Futura CondensedLight  ascent 19680  cap 15440  H adv 8860
# -> the advance table and the glyph shapes share ONE coordinate space, EM = 20480.
SHAPE_EM = 20480       # DefineFont3 coordinate space (= 1024 * 20)

HEBREW = [chr(c) for c in range(0x05D0, 0x05EB)]        # 27 letters
EXTRA = ["־", "׳", "״"]                  # maqaf, geresh, gershayim

ALIGN_ZONE_LEN = 10     # u8 numZoneData(=2) + 2*(2+2) + u8 mask


def _rect(xmin: int, xmax: int, ymin: int, ymax: int) -> bytes:
    nb = _sbits(xmin, xmax, ymin, ymax)
    bw = BitWriter()
    bw.u(nb, 5)
    bw.s(xmin, nb); bw.s(xmax, nb); bw.s(ymin, nb); bw.s(ymax, nb)
    return bw.bytes()


def _cmap(tt):
    for t in tt["cmap"].tables:
        if t.isUnicode():
            return t.cmap
    return tt.getBestCmap()


def _shape_xy(glyphset, glyph_name, sx: float, sy: float) -> bytes:
    """glyph_to_shape() with INDEPENDENT x/y scales (SWF is y-down -> y negated)."""
    pen = ContourPen(glyphset)
    glyphset[glyph_name].draw(pen)

    def tx(pt):
        return (round(pt[0] * sx), round(-pt[1] * sy))

    bw = BitWriter()
    bw.u(1, 4)          # NumFillBits = 1
    bw.u(0, 4)          # NumLineBits = 0
    first = True
    cx = cy = 0
    for c in pen.contours:
        sxp, syp = tx(c["start"])
        bw.u(0, 1)
        mb = _sbits(sxp, syp)
        bw.u(0b00011 if first else 0b00001, 5)
        bw.u(mb, 5)
        bw.s(sxp, mb); bw.s(syp, mb)
        if first:
            bw.u(1, 1)
            first = False
        cx, cy = sxp, syp
        pts = []
        for seg in c["segs"]:
            pts.append(("line", tx(seg[1])) if seg[0] == "line"
                       else ("qcurve", tx(seg[1]), tx(seg[2])))
        if pts and pts[-1][-1] != (sxp, syp):
            pts.append(("line", (sxp, syp)))
        for seg in pts:
            if seg[0] == "line":
                nx, ny = seg[1]
                dx, dy = nx - cx, ny - cy
                if dx == 0 and dy == 0:
                    continue
                bw.u(1, 1); bw.u(1, 1)
                if dx and dy:
                    nb = _sbits(dx, dy); bw.u(nb - 2, 4); bw.u(1, 1)
                    bw.s(dx, nb); bw.s(dy, nb)
                elif dx:
                    nb = _sbits(dx); bw.u(nb - 2, 4); bw.u(0, 1); bw.u(0, 1); bw.s(dx, nb)
                else:
                    nb = _sbits(dy); bw.u(nb - 2, 4); bw.u(0, 1); bw.u(1, 1); bw.s(dy, nb)
                cx, cy = nx, ny
            else:
                (ctx, cty), (anx, any_) = seg[1], seg[2]
                cdx, cdy = ctx - cx, cty - cy
                adx, ady = anx - ctx, any_ - cty
                bw.u(1, 1); bw.u(0, 1)
                nb = _sbits(cdx, cdy, adx, ady); bw.u(nb - 2, 4)
                bw.s(cdx, nb); bw.s(cdy, nb); bw.s(adx, nb); bw.s(ady, nb)
                cx, cy = anx, any_
    bw.u(0, 6)          # EndShapeRecord
    return bw.bytes()


def measure_donor(ttf_path: str, sample: str = "אבגדהוזחטיכלמנסעפצקרשת") -> dict:
    """median Hebrew body height / aspect / advance, in the donor's own font units."""
    import statistics
    from fontTools.ttLib import TTFont
    from fontTools.pens.boundsPen import BoundsPen
    tt = TTFont(ttf_path, fontNumber=0, lazy=False)
    upm = tt["head"].unitsPerEm
    gs, cm, hm = tt.getGlyphSet(), _cmap(tt), tt["hmtx"]
    hs, ws, ad = [], [], []
    for ch in sample:
        gn = cm.get(ord(ch))
        if not gn:
            continue
        bp = BoundsPen(gs); gs[gn].draw(bp)
        if not bp.bounds:
            continue
        x0, y0, x1, y1 = bp.bounds
        hs.append(y1 - y0); ws.append(x1 - x0); ad.append(hm[gn][0])
    tt.close()
    body = statistics.median(hs)
    return {"upm": upm, "body": body, "aspect": statistics.median(ws) / body,
            "adv_ratio": statistics.median(ad) / body}


def make_glyphs(ttf_path: str, chars, *, sx: float, sy: float) -> dict:
    """-> {char: (shape_bytes, advance, bounds_bytes)} in DefineFont3 shape units.

    Bounds are emitted EMPTY on purpose: every one of Skyrim's own 2,041 shipped
    glyphs carries an all-zero RECT, so we match the game's own convention.
    """
    from fontTools.ttLib import TTFont
    tt = TTFont(ttf_path, fontNumber=0, lazy=False)
    gs, cm, hmtx = tt.getGlyphSet(), _cmap(tt), tt["hmtx"]
    empty = _rect(0, 0, 0, 0)
    out = {}
    for ch in chars:
        gn = cm.get(ord(ch))
        if gn is None:
            continue
        out[ch] = (_shape_xy(gs, gn, sx, sy), int(round(hmtx[gn][0] * sx)), empty)
    tt.close()
    return out


def plan_face(face: dict, donor: dict, *, body_ratio: float = 0.86,
              min_condense: float = 0.72) -> tuple[float, float, dict]:
    """Given a MEASURED game face and donor, return (sx, sy, notes).

    sy  : Hebrew body height = body_ratio x the face's Latin cap height.
    sx  : sy x a condensation factor pulled toward the face's own H aspect,
          floored at min_condense so the letterforms never collapse.
    """
    cap = face["cap"]
    target_body = body_ratio * cap
    sy = target_body / donor["body"]
    want = face["H"]["w"] / face["H"]["h"] / donor["aspect"]
    condense = max(min_condense, min(1.0, want))
    sx = sy * condense
    heb_adv = donor["adv_ratio"] * donor["body"] * sx
    return sx, sy, {"cap": cap, "target_body": round(target_body),
                    "condense": round(condense, 3),
                    "heb_adv": round(heb_adv), "latin_H_adv": face["H"]["adv"],
                    "adv_vs_latin": round(heb_adv / face["H"]["adv"], 3)}


def extend_font(f: dict, glyphs: dict, *, overwrite: bool = False) -> tuple[dict, int]:
    """Add glyphs to a parsed DefineFont3. Returns (font, n_added)."""
    if not f["has_layout"]:
        raise ValueError("font has no layout table; cannot extend safely")
    L = f["layout"]
    cur = {c: i for i, c in enumerate(f["codes"])}
    items = []          # (code, shape, advance, bounds)
    for i, c in enumerate(f["codes"]):
        items.append([c, f["shapes"][i], L["advance"][i], L["bounds"][i]])
    added = 0
    for ch, (shape, adv, bounds) in glyphs.items():
        cp = ord(ch)
        if cp in cur:
            if overwrite:
                items[cur[cp]] = [cp, shape, adv, bounds]
            continue
        items.append([cp, shape, adv, bounds])
        added += 1
    items.sort(key=lambda r: r[0])
    f["codes"] = [r[0] for r in items]
    f["shapes"] = [r[1] for r in items]
    L["advance"] = [r[2] for r in items]
    L["bounds"] = [r[3] for r in items]
    f["num"] = len(items)
    # kerning references glyph INDICES only via codes in DefineFont3 (wide codes ->
    # kern pairs store codepoints), so re-sorting is safe; keep the raw block.
    # offset-width guard
    if not f["wide_off"]:
        need = (f["num"] + 1) * 2 + sum(len(s) for s in f["shapes"])
        if need > 0xFFFF:
            f["wide_off"] = True
            f["flags"] |= 0x08
    return f, added


def extend_align_zones(body: bytes, new_num: int) -> bytes:
    """Pad/trim a DefineFontAlignZones tag body so it carries new_num ZoneRecords."""
    head = body[:3]                                    # u16 fontID + u8 hint
    zones = body[3:]
    have = len(zones) // ALIGN_ZONE_LEN
    if have == new_num:
        return body
    if have > new_num:
        return head + zones[:new_num * ALIGN_ZONE_LEN]
    neutral = bytes([2]) + b"\x00" * 8 + b"\x00"
    return head + zones + neutral * (new_num - have)


def inject_swf(src: str | Path, dst: str | Path, faces: dict[int, str], chars=None,
               body_ratio: float = 0.86, verbose: bool = True) -> dict:
    """faces = {font_id: ttf_path}. Scale is PLANNED per face from its own metrics."""
    chars = chars or (HEBREW + EXTRA)
    s = SWF.read(src)
    dcache: dict[str, dict] = {}
    report: dict = {}
    new_num_by_id: dict[int, int] = {}
    for t in s.tags:
        if t.code != SWF.DEFINE_FONT3:
            continue
        f = parse_definefont3(t.body)
        fid = f["font_id"]
        if fid not in faces:
            continue
        ttf = faces[fid]
        if ttf not in dcache:
            dcache[ttf] = measure_donor(ttf)
        m = measure_face(f)
        if "cap" not in m or "H" not in m:
            raise ValueError(f"font {fid}: cannot measure a cap height")
        sx, sy, notes = plan_face(m, dcache[ttf], body_ratio=body_ratio)
        glyphs = make_glyphs(ttf, chars, sx=sx, sy=sy)
        # every generated shape must survive our own parser (Scaleform is stricter)
        for ch, (sh, _a, _b) in glyphs.items():
            if shape_bbox(sh) is None and ch != " ":
                raise ValueError(f"font {fid}: empty shape for {ch!r}")
        before = len(f["codes"])
        f, added = extend_font(f, glyphs)
        body = serialize_definefont3(f)
        chk = parse_definefont3(body)
        assert chk["codes"] == f["codes"], f"font {fid}: code table did not survive"
        assert chk["shapes"] == f["shapes"], f"font {fid}: shapes did not survive"
        assert chk["codes"] == sorted(chk["codes"]), f"font {fid}: codes not ascending"
        t.body = body
        new_num_by_id[fid] = f["num"]
        heb = sum(1 for c in f["codes"] if 0x05D0 <= c <= 0x05EA)
        report[fid] = {"name": f["name"].rstrip(b"\x00").decode("latin1"),
                       "donor": Path(ttf).name, "before": before, "after": f["num"],
                       "added": added, "hebrew": heb, "wide_off": f["wide_off"],
                       "bytes": len(body), **notes}
        if verbose:
            r = report[fid]
            print(f"   id={fid:<3} {r['name']:<30} <- {r['donor']:<26} "
                  f"{before}->{f['num']} heb={heb}/27 cap={notes['cap']} "
                  f"body={notes['target_body']} cond={notes['condense']} "
                  f"advVsLatin={notes['adv_vs_latin']} wideO={f['wide_off']}")
    # keep the align-zone tags consistent
    for t in s.tags:
        if t.code == SWF.DEFINE_FONT_ALIGN_ZONES and len(t.body) >= 3:
            fid = struct.unpack_from("<H", t.body, 0)[0]
            if fid in new_num_by_id:
                t.body = extend_align_zones(t.body, new_num_by_id[fid])
    out = s.pack()
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_bytes(out)
    # final read-back from DISK
    v = SWF.read(dst)
    ok = 0
    for t in v.tags:
        if t.code == SWF.DEFINE_FONT3:
            g = parse_definefont3(t.body)
            if g["font_id"] in faces:
                assert g["codes"] == sorted(g["codes"])
                ok += sum(1 for c in g["codes"] if 0x05D0 <= c <= 0x05EA) >= 27
    if verbose:
        print(f"   -> {dst}  {Path(src).stat().st_size} -> {len(out)} B  "
              f"(faces with full Hebrew on re-read: {ok}/{len(report)})")
    return report


def audit(path: str | Path) -> None:
    s = SWF.read(path)
    for t in s.tags:
        if t.code == SWF.DEFINE_FONT3:
            f = parse_definefont3(t.body)
            heb = sum(1 for c in f["codes"] if 0x05D0 <= c <= 0x05EA)
            print(f"  id={f['font_id']:<3} {f['name'].rstrip(bytes([0])).decode('latin1'):<32} "
                  f"glyphs={f['num']:<5} heb={heb}/27")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "audit":
        audit(sys.argv[2])
    else:
        print(__doc__)
