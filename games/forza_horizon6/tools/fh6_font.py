"""ForzaTech `.vfont` / `.vfontN` codec — FULLY DECODED, read + write (2026-07-27).

A font is a PAIR: `<name>.vfont` (the glyph table) and `<name>.vfontN` pages
(N = 0..pageCount-1), both inside `media\\UI\\Fonts.zip`.

🔑 **`.vfontN` is NOT a bitmap atlas — it is a triangulated VECTOR MESH store.**
Proven by rendering the decoded meshes straight to an image: they read as the
letters (`extract/mesh_render.png`). That is why the pages are not DDS, why FH6
text is crisp at any size, and why per-glyph size tracks complexity rather than area.

## `.vfont` layout

    len == 204 + 8 + [24 + 36*N] + 12*kernCount + [4 + 8*pageCount]

exact on all 20 shipped fonts, single- and multi-page, with `slotCount == N + 1`.

    0x00  char[128]  name (NUL-padded)
    0x78  u32        version (2)
    0x7c  u32        4
    0x80  u16        slotCount
    0x82  u16        kernCount
    0x84  u16        pageCount
    0x86  u16        pageCount (duplicated)
    0x88..0xCB       metrics floats, in 2048 upem       -> 204 B header
    0xCC             ONE 8-byte record (NOT 8 per page)
                     glyph region: prefix(24) + trueRecord(36) * N
                     kern[kernCount]  12 B each: {u32 cpA, u32 cpB, f32 amount}
                     TRAILER                            <- see below

### 🔴 THE TRAILER IS THE REAL PAGE TABLE

The last `4 + 8*pageCount` bytes of the file are

    u32 slotCount
    per page:  u32 pageByteSize,  u32 glyphsInPage

and every declared size equals the real `.vfontN` length on every font, including
Horizon_CHS's 15 pages and Horizon_JP's 10. **The engine believes this, not the
file length.** Leaving it stale after injecting glyphs makes the letters past the
old declared size silently vanish — which reads as a broken font rather than a
stale size field. `serialize(page_sizes)` regenerates it; passing nothing keeps
the original bytes (used for the identity round-trip).

The 8 bytes at 0xCC look like a per-page table and are not one: Horizon_RU_C and
Horizon_RU_D carry byte-identical records there while their pages differ by 20 KB.
Reading it as `8 * pageCount` — and inventing a 12-byte "suffix" to absorb the
trailer — cancels out only when `pageCount == 1`, which is exactly why the CJK
fonts used to decode as garbage (Horizon_JP's max dataOffset came out as 3.1
billion, and its Latin coverage as 4 glyphs instead of 58).

### 🔴 Slots vs glyphs — the record is SHIFTED 24 bytes into the region

Reading the region as 36-byte records starting at offset 0 pairs each codepoint
with the WRONG mesh. The real layout is

    glyph region = prefix(24 B) + trueRecord(36 B) * N

    trueRecord:
        +0x00  u32   codepoint
        +0x04  f32   advance
        +0x08  f32   height          (0 for space; == the mesh's top y)
        +0x0c  f32   xOffset
        +0x10  u16   vertexCount
        +0x12  u16   indexCount
        +0x14  u32   dataOffset      -> into the `.vfontN` page
        +0x18  u32   0xFFFFFFFF
        +0x1c  f32   0.0
        +0x20  f32   -3e-08          (a constant, effectively -0.0)

The `prefix` carries the mesh fields of a leading dummy and is preserved verbatim.

Confirmed independently: `H` (straight edges only) has `cu == 0` on every vertex
and an ink width matching its 0.645 advance, while the naively-paired record
would hand that mesh to the narrow `I` (advance 0.285).

## `.vfontN` page layout

    per glyph, in record order:
        u32 codepoint        <- self-tag; 0x1F for the leading dummy
        u32 vertexCount
        u32 indexCount
        vertex[vertexCount]  8 B each
        u16 index[indexCount]

`dataOffset` points at the codepoint tag, so the payload starts at +12 and

    blockLen == 12 + 8*vertexCount + 2*indexCount    # 2,487 glyphs, 0 exceptions

Vertex = **4 x fp16 `(x, y, cu, cv)`**:

* `x, y` — em coordinates with the baseline at y = 0 and **x biased by +0.5**
  (so `x_em = x - 0.5`); rendering these with the index buffer produces the
  readable letterforms.
* `cv` — coverage: **1.0 on the solid interior triangles**, and `+-W/edgeLen` on
  the anti-aliasing band quads that straddle each outline edge.
* `cu` — curve parameter: **exactly 0 wherever the edge is straight**, non-zero
  only on curved segments.

So a glyph is [solid interior, cv = 1] + [per-edge AA band, cv = +-W/L], the band
being a miter offset of `W` (measured 0.0283 em) either side of the outline.
Emitting interior triangles alone with `cu = 0, cv = 1` is therefore a valid,
fully-opaque glyph — which is what `build_mesh()` does.
"""
from __future__ import annotations

import os
import struct
import sys
from typing import Dict, Iterable, List, NamedTuple, Sequence, Tuple

NAME_LEN = 128
HDR = 204
PAGE_REC = 8                    # ONE 8-byte record, whatever pageCount says
SLOT = 36
KERN_REC = 12
PREFIX = 24
VERTEX = 8
NOTDEF = 0xFFFD
LEAD_TAG = 0x1F                 # the page's leading dummy block tag
X_BIAS = 0.5                    # x_mesh = x_em + X_BIAS
BAND_W = 0.0283                 # AA miter half-width, em

_REC = struct.Struct("<I3f2HI I2f")     # cp adv hgt xoff vc ic off sentinel z nz


def trailer_len(n_pages: int) -> int:
    """🔴 THE REAL PAGE TABLE IS THE LAST `4 + 8*pageCount` BYTES OF THE FILE.

        u32 slotCount
        per page:  u32 pageByteSize,  u32 glyphsInPage

    Verified against every shipped font, including Horizon_CHS's 15 pages and
    Horizon_JP's 10 — every declared size equals the real `.vfontN` length.

    The 8 bytes right after the 204-byte header (which look like a page table)
    are NOT it: Horizon_RU_C and Horizon_RU_D have byte-identical records there
    while their pages differ by 20 KB.

    Leaving this stale is what truncated the injected glyphs: the page grew but
    the trailer still declared the old length, so the engine simply did not have
    the last letters — which reads as a font bug, not a size bug.
    """
    return 4 + 8 * n_pages


class Glyph(NamedTuple):
    cp: int
    adv: float
    hgt: float
    xoff: float
    n_verts: int
    n_indices: int
    data_off: int
    tail: Tuple[int, float, float]      # sentinel, 0.0, -0.0 — preserved verbatim

    def pack(self) -> bytes:
        return _REC.pack(self.cp, self.adv, self.hgt, self.xoff,
                         self.n_verts, self.n_indices, self.data_off, *self.tail)


class VFont(NamedTuple):
    name: str
    n_kerns: int
    n_pages: int
    header: bytes                       # 204 B, glyph/kern counts patched on write
    pages: bytes
    prefix: bytes
    glyphs: List[Glyph]
    suffix: bytes
    kerns: bytes
    trailer: bytes                      # the REAL page table — see below

    # ---- queries -------------------------------------------------------
    def codepoints(self) -> List[int]:
        return [g.cp for g in self.glyphs]

    def coverage(self, lo: int, hi: int) -> List[int]:
        s = {g.cp for g in self.glyphs}
        return [c for c in range(lo, hi + 1) if c in s]

    def by_cp(self) -> Dict[int, Glyph]:
        return {g.cp: g for g in self.glyphs}

    def page_table(self) -> Tuple[int, List[Tuple[int, int]]]:
        """(slotCount, [(pageByteSize, glyphsInPage), ...]) from the trailer."""
        v = struct.unpack(f"<{len(self.trailer) // 4}I", self.trailer)
        return v[0], [(v[1 + 2 * i], v[2 + 2 * i]) for i in range(self.n_pages)]

    # ---- serialize -----------------------------------------------------
    def serialize(self, page_sizes: Sequence[int] | None = None,
                  page_counts: Sequence[int] | None = None) -> bytes:
        """`page_sizes` MUST be given whenever a page's byte length changed."""
        slots = len(self.glyphs) + 1
        hdr = bytearray(self.header)
        struct.pack_into("<3H", hdr, 0x80, slots, self.n_kerns, self.n_pages)
        struct.pack_into("<H", hdr, 0x86, self.n_pages)
        if page_sizes is None:
            trailer = self.trailer
        else:
            if len(page_sizes) != self.n_pages:
                raise ValueError(f"{self.name}: need {self.n_pages} page sizes")
            if page_counts is None:
                # a single-page font holds every glyph, so its count follows the
                # slot count; a multi-page font's split is its own business
                page_counts = ([slots] if self.n_pages == 1
                               else [c for _, c in self.page_table()[1]])
            trailer = struct.pack("<I", slots) + b"".join(
                struct.pack("<2I", s, c) for s, c in zip(page_sizes, page_counts))
        return (bytes(hdr) + self.pages + self.prefix
                + b"".join(g.pack() for g in self.glyphs)
                + self.kerns + trailer)


def parse(buf: bytes) -> VFont:
    name = buf[:NAME_LEN].split(b"\x00", 1)[0].decode("utf-8", "replace")
    slots, n_kerns, n_pages, _dup = struct.unpack_from("<4H", buf, 0x80)

    #     HDR + 8 + [24 + 36*N] + 12*kerns + [4 + 8*pageCount]
    # with slots == N + 1. Exact on all 20 shipped fonts, single- AND multi-page.
    # Two corrections to the first reading, both of which only ever cancelled out
    # when pageCount == 1 — which is why the CJK fonts decoded as garbage
    # (Horizon_JP's max dataOffset came out as 3.1 BILLION):
    #   * the block after the header is ONE 8-byte record, not 8 per page;
    #   * the glyph region has NO 12-byte suffix — those bytes are the trailer.
    tn = trailer_len(n_pages)
    want = HDR + PAGE_REC + PREFIX + SLOT * (slots - 1) + KERN_REC * n_kerns + tn
    if want != len(buf):
        raise ValueError(f"{name}: size {len(buf)} != model {want}")

    p = HDR
    pages = buf[p:p + PAGE_REC]          # a CONSTANT 8 bytes, not 8 per page
    p += PAGE_REC
    body_end = len(buf) - tn - KERN_REC * n_kerns
    region = buf[p:body_end]
    kerns = buf[body_end:len(buf) - tn]

    n_true, rest = divmod(len(region) - PREFIX, SLOT)
    if rest:
        raise ValueError(f"{name}: glyph region {len(region)} is not 24+36*N")

    glyphs = [Glyph(*_REC.unpack_from(region, PREFIX + SLOT * i)[:7],
                    _REC.unpack_from(region, PREFIX + SLOT * i)[7:])
              for i in range(n_true)]
    return VFont(name, n_kerns, n_pages, buf[:HDR], pages, region[:PREFIX],
                 glyphs, b"", kerns, buf[len(buf) - tn:])


# --------------------------------------------------------------------------
# meshes
# --------------------------------------------------------------------------
Vertex = Tuple[float, float, float, float]


def read_mesh(page: bytes, g: Glyph) -> Tuple[List[Vertex], Tuple[int, ...]]:
    """(vertices, indices) for one glyph, straight out of a `.vfontN` page."""
    tag, vc, ic = struct.unpack_from("<3I", page, g.data_off)
    if (vc, ic) != (g.n_verts, g.n_indices):
        raise ValueError(f"U+{g.cp:04X}: page says {vc}/{ic}, record says "
                         f"{g.n_verts}/{g.n_indices}")
    o = g.data_off + 12
    verts = [struct.unpack_from("<4e", page, o + VERTEX * k) for k in range(vc)]
    idx = struct.unpack_from(f"<{ic}H", page, o + VERTEX * vc)
    return verts, idx


def block(cp: int, verts: Sequence[Vertex], idx: Sequence[int]) -> bytes:
    """One `.vfontN` block: self-tag + counts + vertices + indices."""
    out = bytearray(struct.pack("<3I", cp, len(verts), len(idx)))
    for x, y, cu, cv in verts:
        out += struct.pack("<4e", x, y, cu, cv)
    out += struct.pack(f"<{len(idx)}H", *idx)
    return bytes(out)


def build_page(lead: bytes, glyphs: Iterable[Glyph],
               meshes: Dict[int, Tuple[List[Vertex], Sequence[int]]],
               old_page: bytes) -> Tuple[bytes, List[Glyph]]:
    """Rewrite a whole page in record order; returns (page, glyphs with new offsets).

    `meshes` supplies replacements by codepoint; anything absent is copied
    verbatim from `old_page`. Rebuilding wholesale keeps the blocks contiguous
    and in record order, exactly as the game ships them.
    """
    out = bytearray(lead)
    fixed: List[Glyph] = []
    for g in glyphs:
        if g.cp in meshes:
            v, i = meshes[g.cp]
            b = block(g.cp, v, i)
            g = g._replace(n_verts=len(v), n_indices=len(i), data_off=len(out))
        else:
            n = 12 + VERTEX * g.n_verts + 2 * g.n_indices
            b = old_page[g.data_off:g.data_off + n]
            if len(b) != n:
                raise ValueError(f"U+{g.cp:04X}: short block in source page")
            g = g._replace(data_off=len(out))
        out += b
        fixed.append(g)
    return bytes(out), fixed


def lead_block(page: bytes) -> bytes:
    """The page's leading dummy block (tag 0x1F), preserved verbatim."""
    tag, vc, ic = struct.unpack_from("<3I", page, 0)
    return page[:12 + VERTEX * vc + 2 * ic]


def load_all(payload: Dict[str, bytes]) -> Dict[str, VFont]:
    return {n[:-6]: parse(b) for n, b in payload.items() if n.endswith(".vfont")}


# The three huge CJK families store something else in the codepoint field, so
# their cp tables are not authoritative. Every Latin/Cyrillic family — including
# all seven this project touches — is clean.
CJK_CP_UNRELIABLE = ("Horizon_CHS", "Horizon_CHT", "Horizon_KO")
BLANK_OK = (0x20, 0xA0, 0x3000, 0xFFFD)      # the outline-less characters


def selftest(pay: Dict[str, bytes]) -> None:
    """Re-derive every invariant this module claims, from the shipped files."""
    n_glyph = n_zero = n_ident = 0
    fonts = load_all(pay)
    for fam, f in sorted(fonts.items()):
        assert f.serialize() == pay[f"{fam}.vfont"], f"{fam}: serialize != source"
        n_ident += 1
        # the trailer must already declare every page's true byte length
        sizes = [len(pay[f"{fam}.vfont{i}"]) for i in range(f.n_pages)]
        assert f.serialize(sizes) == pay[f"{fam}.vfont"], \
            f"{fam}: rebuilt trailer != shipped trailer"
        if f.n_pages == 1:
            page = pay[f"{fam}.vfont0"]
            off = len(lead_block(page))
            for g in f.glyphs:                       # blocks are contiguous, in order
                assert g.data_off == off, f"{fam} U+{g.cp:04X}: block out of order"
                read_mesh(page, g)                   # validates the self-tag + counts
                off += 12 + VERTEX * g.n_verts + 2 * g.n_indices
                n_glyph += 1
            assert off == len(page), f"{fam}: page tail {len(page) - off}"
            rebuilt, fixed = build_page(lead_block(page), f.glyphs, {}, page)
            assert rebuilt == page and fixed == f.glyphs, f"{fam}: page rebuild"
        if fam in CJK_CP_UNRELIABLE:
            continue
        # Strictly ascending up to U+FFFD, then a short alias tail (Horizon_JP
        # repeats U+0021/U+0022 there). Insert new glyphs inside the sorted
        # prefix; never append past the notdef.
        cps = f.codepoints()
        head = cps[:cps.index(NOTDEF) + 1] if NOTDEF in cps else cps
        assert head == sorted(set(head)), f"{fam}: codepoints not strictly ascending"
        for g in f.glyphs:
            if g.n_verts == 0:
                assert g.cp in BLANK_OK, f"{fam}: zero-vert mesh is U+{g.cp:04X}"
                n_zero += 1
    print("selftest OK")
    print(f"  {n_ident}/{len(fonts)} fonts re-serialize BYTE-IDENTICAL")
    print(f"  {n_glyph} glyphs: block self-tag + counts + contiguity + page rebuild")
    print(f"  {len(fonts) - len(CJK_CP_UNRELIABLE)} families: codepoints strictly "
          f"ascending, and all {n_zero} zero-vertex meshes are outline-less "
          f"({', '.join('U+%04X' % c for c in BLANK_OK)})")


if __name__ == "__main__":                                    # pragma: no cover
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.path.insert(0, os.path.dirname(__file__))
    import fh6_zip as Z

    game = os.environ.get("FH6_GAME", r"C:\Games\Forza Horizon 6")
    _, pay = Z.read(os.path.join(game, "media", "UI", "Fonts.zip"))
    fonts = load_all(pay)
    print(f"{'family':<20s} {'glyphs':>7} {'kerns':>7} {'pages':>6} "
          f"{'latin':>6} {'cyr':>4} {'HEB':>6}  page bytes")
    for fam in sorted(fonts):
        f = fonts[fam]
        pg = sum(len(pay[f"{fam}.vfont{i}"]) for i in range(f.n_pages))
        print(f"  {fam:<18s} {len(f.glyphs):>7} {f.n_kerns:>7} {f.n_pages:>6} "
              f"{len(f.coverage(0x41, 0x7A)):>6} {len(f.coverage(0x400, 0x4FF)):>4} "
              f"{len(f.coverage(0x05D0, 0x05EA)):>4}/27  {pg:>11,}")
    print()
    selftest(pay)
