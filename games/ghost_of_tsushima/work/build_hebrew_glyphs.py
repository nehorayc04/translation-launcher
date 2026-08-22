#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""build_hebrew_glyphs.py — Ghost of Tsushima DC Hebrew font injection (round 7, 2026-07-08).

HONEST STATUS: the FONT gate is NOT closed. Real Hebrew glyph OUTLINES were NOT injected.
Two of the three pipeline stages WORK and are implemented here for real; the third is BLOCKED
on a proprietary vertex codec that cannot be cracked offline (needs the exe's FontVerts decoder).

  STAGE 1  (WORKS, implemented) : extract the 27 Hebrew glyph outlines U+05D0..05EA from
                                  C:/Windows/Fonts/david.ttf via fontTools, flatten + ascii-raster
                                  them (proves the SOURCE outlines are in hand). `--contours`
  STAGE 2  (WORKS, implemented) : the container/record/deploy mechanism. The 27 Hebrew cmap
                                  records are same-size editable; a gold-validated deployable
                                  override (`gapack_misc_g_mechproof.psarc`) is (re)built via the
                                  proven surgical DSAR editor. `--mechproof`
  STAGE 3  (BLOCKED)            : ENCODE the Stage-1 contours into the shipping vertex STORE format
                                  ("store8" @0x8b0000) and repoint the 27 Hebrew records at them.
                                  The store is a proprietary bit-packed/quantized 8-byte-unit format
                                  (NOT floats/int16, NOT zlib/lz4/oodle, NOT encrypted). Encoding a
                                  NEW glyph into it needs the exe's decoder spec. `--real` -> reports
                                  the exact blocker and writes NOTHING fake.

WHY STAGE 3 IS BLOCKED (all verified this round against the real cached ghost_title.xpps,
md5 3d5d62aa44dacd44640ed132493ab6db, run with the repo .venv python):

  * The glyph outline VERTEX STORE is "store8" @0x8b0000..0x8b74b0 (29,872 B = 3733 x 8-byte units),
    the ONLY dense region inside the font sub-resource (0x850c00..0x8b74b0). It is:
      - PACKED, not encrypted: one 8-byte unit repeats x111, a 16-byte pair repeats x56, and the
        dominant byte-match lag is 8 (then 16,24,32,48). Encryption would show zero repeats + flat lags.
      - NOT plain coordinates: as f16/i16/f32 the units trace to unbounded garbage (range +-65440),
        50% out of [-2,2]; every plaintext-coordinate hypothesis (i16, i8-delta, f16, f32, 11-bit,
        cumulative-delta) FAILS to trace a bounded closed contour (this round + vertstore.py round 3).
      - NOT standard-compressed: lead byte 0x1f; zlib(all wbits)/lz4.block/oodle-lead all fail.
    => a proprietary quantized vertex packing whose bit-layout is only in the exe's decode path.

  * RESOLUTION CHAIN (shape known, this round): cmap record `+16` = outline-id (real glyphs
    1269..3496, 283 distinct) -> a descriptor table @0x8aed12 (16-byte stride, ascending outline-id
    at +6, small vertex/index COUNT at +8: 23,28,36,42..) -> the store + the plaintext u16 index
    buffers @0x851000. So WHICH bytes belong to a glyph is derivable; HOW those bytes encode the
    vertices is the missing piece.

  * The "tail kind2" region 0x97c8d0..0x9a2750 (155 KB) that a prior pass called the "best FontVerts
    candidate (normalized floats in [-1,1])" is REFUTED here: only 48% of its floats are in [-1,1],
    32% are huge (~5e31), and it contains a repeated UNIT QUATERNION [-0.8133,-0.3398,0.4724,0.1522] x3
    -> it is title-card sprite TRANSFORM data (pos/quat/scale), NOT glyph vertices.

  THE EXACT BLOCKER: the store8 8-byte-unit bit layout (quantization scheme + how a glyph's vertex
  run + the u16 index list reconstruct contours). Crack it by RE of GhostOfTsushima.exe's SFontData /
  FontVerts / GENERATE_QUAD loader (image base 0x140000000; the FONTK/handler cluster near exe
  0x011628F8 / the string cluster near 0x1107f10). That is an exe-disassembly sub-project, out of
  scope for offline KCAP analysis. Until then a real Hebrew vector glyph cannot be synthesized.

DELIVERABLE (this round): the STAGE-2 mechanism-proof override `gapack_misc_g_mechproof.psarc`
(built by work/build_font_mechproof.py, gold-validated by work/validate_mechproof.py). Deploying it
and looking in-game (Text=Arabic) tells the human whether repointing the cmap ref even changes the
rendered glyph -> it resolves the last static ambiguity (is the shape addressed by the record, or by
the codepoint via an external store) and tells the exe-RE pass exactly what to target.

Usage (repo .venv python):
  python build_hebrew_glyphs.py --contours    # STAGE 1: david Hebrew outlines + ascii raster (offline)
  python build_hebrew_glyphs.py --mechproof   # STAGE 2: (re)build the deployable override + deploy cmds
  python build_hebrew_glyphs.py --real        # STAGE 3: attempt real injection -> reports the blocker
  python build_hebrew_glyphs.py               # status + blocker + deploy commands for the existing artifact

Writes ONLY to the scratch dir. No file under F:/Games/... is modified (the human deploys).
"""
import os, sys, struct, importlib.util, argparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(GAME_DIR))
GAME = os.environ.get("GOT_GAME", r"F:/Games/Ghost of Tsushima DC")
GG = os.path.join(GAME, "cache_pc", "psarc", "gapack_misc_g.psarc")
SCRATCH = (r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/"
           r"c--Users-Nehoray-Cohen-Projects-Game-translator/"
           r"a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad")
MECHPROOF = os.path.join(SCRATCH, "gapack_misc_g_mechproof.psarc")
DAVID = r"C:/Windows/Fonts/david.ttf"

HEB_CP0, NHEB = 0x05D0, 27                      # alef..tav (U+05D0..05EA)
HEB_CPS = list(range(HEB_CP0, HEB_CP0 + NHEB))

# --- verified store facts (this round) -------------------------------------------------
STORE8 = (0x8B0000, 0x8B74B0)                   # packed vertex store (29,872 B, 8-byte units)
CMAP = (0x866952, 0x8AEC92)                      # 64-byte codepoint records
DESC_TABLE = 0x8AED12                            # outline-id -> count descriptor table (16B stride)
IDX_BUF = 0x851000                               # plaintext u16 triangle/vertex index buffers


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


# =======================================================================================
# STAGE 1 — extract the 27 Hebrew glyph outlines from david.ttf  (WORKS, real)
# =======================================================================================
def extract_david_hebrew_contours(unitsPerEm_norm=True):
    """Return {cp: [contour, ...]} where each contour is a list of (x, y) on-curve points
    (quadratics flattened). Coordinates optionally normalized to the em square [0,1]. This is
    the SOURCE geometry the Stage-3 encoder would consume. Fully offline via fontTools."""
    from fontTools.ttLib import TTFont
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.pens.basePen import BasePen

    font = TTFont(DAVID)
    upem = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    glyphset = font.getGlyphSet()

    class _FlattenPen(BasePen):
        """Collect contours as polylines; flatten quadratics with a few segments."""
        def __init__(self, glyphSet):
            super().__init__(glyphSet); self.contours = []; self._cur = None; self._last = None
        def _moveTo(self, p):
            self._cur = [p]; self._last = p
        def _lineTo(self, p):
            self._cur.append(p); self._last = p
        def _curveToOne(self, c1, c2, p):
            self._flatten_cubic(self._last, c1, c2, p); self._last = p
        def _qCurveToOne(self, c, p):
            self._flatten_quad(self._last, c, p); self._last = p
        def _flatten_quad(self, p0, c, p1, n=8):
            for i in range(1, n + 1):
                t = i / n; mt = 1 - t
                x = mt * mt * p0[0] + 2 * mt * t * c[0] + t * t * p1[0]
                y = mt * mt * p0[1] + 2 * mt * t * c[1] + t * t * p1[1]
                self._cur.append((x, y))
        def _flatten_cubic(self, p0, c1, c2, p1, n=10):
            for i in range(1, n + 1):
                t = i / n; mt = 1 - t
                x = mt**3 * p0[0] + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t**3 * p1[0]
                y = mt**3 * p0[1] + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t**3 * p1[1]
                self._cur.append((x, y))
        def _closePath(self):
            if self._cur:
                self.contours.append(self._cur); self._cur = None
        def _endPath(self):
            self._closePath()

    out = {}
    for cp in HEB_CPS:
        gname = cmap.get(cp)
        if not gname:
            out[cp] = []
            continue
        pen = _FlattenPen(glyphset)
        glyphset[gname].draw(pen)
        pen._closePath()
        cs = pen.contours
        if unitsPerEm_norm:
            cs = [[(x / upem, y / upem) for (x, y) in c] for c in cs]
        out[cp] = cs
    font.close()
    return out


def ascii_raster(contours, w=24, h=18):
    """Fill-rasterize a glyph's contours (normalized coords) to an ascii grid — proves the
    Stage-1 outline is a real letter shape, offline, with no game/codec dependency."""
    if not contours:
        return ["(no glyph)"]
    xs = [x for c in contours for (x, _) in c]; ys = [y for c in contours for (_, y) in c]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sx = (w - 1) / (x1 - x0) if x1 > x0 else 1.0
    sy = (h - 1) / (y1 - y0) if y1 > y0 else 1.0

    def inside(px, py):
        c = False
        for cont in contours:
            n = len(cont)
            for i in range(n):
                ax, ay = cont[i]; bx, by = cont[(i + 1) % n]
                if (ay > py) != (by > py):
                    xint = ax + (py - ay) * (bx - ax) / (by - ay + 1e-12)
                    if px < xint:
                        c = not c
        return c

    grid = []
    for row in range(h):
        py = y1 - row / sy
        line = "".join("#" if inside(x0 + col / sx, py) else " " for col in range(w))
        grid.append(line)
    return grid


def cmd_contours():
    print(f"STAGE 1 — david.ttf Hebrew outlines (U+05D0..05EA), offline via fontTools")
    cs = extract_david_hebrew_contours()
    names = {0x5D0: "alef", 0x5D1: "bet", 0x5E9: "shin", 0x5EA: "tav", 0x5DE: "mem", 0x5DC: "lamed"}
    total = sum(len(v) for v in cs.values())
    print(f"extracted {sum(1 for v in cs.values() if v)}/27 glyphs, {total} contours total\n")
    for cp in (0x5D0, 0x5D1, 0x5E9, 0x5DC):        # alef, bet, shin, lamed
        print(f"U+{cp:04X} {names.get(cp,''):5} — {len(cs[cp])} contour(s):")
        for line in ascii_raster(cs[cp]):
            print("   |" + line + "|")
        print()
    print("=> STAGE 1 works: the 27 Hebrew source outlines are in hand and render as real letters.")
    print("   The ONLY missing step is STAGE 3: encoding them into the shipping store8 format (BLOCKED).")
    return cs


# =======================================================================================
# STAGE 3 — the blocked encoder
# =======================================================================================
class StoreCodecBlocked(NotImplementedError):
    pass


def encode_store8_units(vertices, indices):
    """Would encode a tessellated glyph mesh (vertices + u16 indices) into the shipping
    "store8" 8-byte-unit packed format and return the bytes to splice at 0x8B0000 + repoint.
    BLOCKED: the 8-byte-unit bit layout is a proprietary quantization only defined in the exe's
    FontVerts decoder (verified opaque: not floats/int16, not zlib/lz4/oodle, not encrypted)."""
    raise StoreCodecBlocked(
        "store8 8-byte-unit codec unknown — proprietary bit-packed quantization; "
        "crack via RE of GhostOfTsushima.exe SFontData/FontVerts/GENERATE_QUAD loader "
        "(image base 0x140000000). Offline known-plaintext exhausted (round 3 + round 7).")


def cmd_real():
    print("STAGE 3 — attempt the REAL Hebrew outline injection\n")
    cs = extract_david_hebrew_contours()
    print(f"  Stage 1 OK: {sum(1 for v in cs.values() if v)}/27 david Hebrew outlines extracted.")
    print("  Stage 3: encoding contours -> store8 units ...")
    try:
        encode_store8_units([], [])
    except StoreCodecBlocked as e:
        print(f"\n  *** BLOCKED: {e}\n")
        print("  NOTHING written (no fake glyphs). The deployable STAGE-2 mechanism-proof is the")
        print("  deliverable for now — run:  python build_hebrew_glyphs.py --mechproof")
    return 2                                       # non-zero: real injection not done


# =======================================================================================
# STAGE 2 — (re)build the deployable mechanism-proof override  (WORKS, real)
# =======================================================================================
def cmd_mechproof(fields="ref"):
    print("STAGE 2 — (re)build the gold-validated mechanism-proof override\n")
    bfm = _load("build_font_mechproof", os.path.join(HERE, "build_font_mechproof.py"))
    out, sz, src = bfm.build(fields)
    return out


def _verify_existing_mechproof():
    if not os.path.exists(MECHPROOF):
        return None
    try:
        dsar = _load("dsar", os.path.join(REPO, "games", "tlou2", "tools", "dsar.py"))
        v = dsar.Psarc2(MECHPROOF)
        e = next(x for x in v.files() if x.path == "/ghost_title.xpps")
        vx = v.extract(e)
        cps = [struct.unpack_from("<H", vx, 0x87EC92 + i * 64)[0] for i in range(NHEB)]
        refs = {(struct.unpack_from("<H", vx, 0x87EC92 + i * 64 + 14)[0],
                 struct.unpack_from("<H", vx, 0x87EC92 + i * 64 + 16)[0],
                 struct.unpack_from("<H", vx, 0x87EC92 + i * 64 + 18)[0]) for i in range(NHEB)}
        v.d.f.close()
        ok = cps == HEB_CPS and len(refs) == NHEB and len(vx) == 10_103_200
        return dict(files=v.num_files, size=os.path.getsize(MECHPROOF),
                    cps_intact=cps == HEB_CPS, distinct_refs=len(refs), valid=ok)
    except Exception as ex:
        return dict(error=str(ex))


def cmd_status():
    print(__doc__.split("Usage")[0])
    m = _verify_existing_mechproof()
    print("--- STAGE-2 deliverable (mechanism-proof override) ---")
    if m is None:
        print(f"  NOT built yet. Build it:  python build_hebrew_glyphs.py --mechproof")
    elif m.get("valid"):
        print(f"  EXISTS + VALID: {MECHPROOF}")
        print(f"    files={m['files']}  size={m['size']:,} B  27 Hebrew cps intact={m['cps_intact']}  "
              f"distinct refs={m['distinct_refs']}/27 (shipping was 3/27 degenerate)")
    else:
        print(f"  present but check: {m}")
    bak = GG + ".he_backup"
    print("\n--- DEPLOY the mechanism-proof (human; resolves the record<->shape question in-game) ---")
    print(f'  Copy-Item -Force "{GG}" "{bak}"')
    print(f'  Copy-Item -Force "{MECHPROOF}" "{GG}"')
    print("  launch -> Settings -> Options -> General -> Text Language = العربية")
    print("  LOOK at the menu Hebrew (New Game/Options/Subtitles): do the 27 Hebrew slots now show")
    print("  27 real ARABIC letters (not tofu)?  YES => the cmap ref addresses the shape (repoint works,")
    print("  only the store codec remains).  STILL TOFU => the shape is keyed elsewhere (codepoint store).")
    print(f'\n--- REVERT ---\n  Copy-Item -Force "{bak}" "{GG}"   (or Steam/Epic: Verify Integrity)')
    print("\n--- THE font gate (STAGE 3, BLOCKED) ---")
    print("  Real Hebrew glyphs need the store8 8-byte-unit codec (proprietary bit-packing).")
    print("  Next: RE GhostOfTsushima.exe SFontData/FontVerts/GENERATE_QUAD loader. See module docstring.")


def main():
    ap = argparse.ArgumentParser(description="GoT DC Hebrew font injection (round 7)")
    ap.add_argument("--contours", action="store_true", help="STAGE 1: david Hebrew outlines + ascii raster")
    ap.add_argument("--mechproof", action="store_true", help="STAGE 2: (re)build the deployable override")
    ap.add_argument("--fields", choices=["ref", "full"], default="ref")
    ap.add_argument("--real", action="store_true", help="STAGE 3: attempt real injection -> reports blocker")
    a = ap.parse_args()
    if a.contours:
        cmd_contours()
    elif a.mechproof:
        cmd_mechproof(a.fields)
    elif a.real:
        sys.exit(cmd_real())
    else:
        cmd_status()


if __name__ == "__main__":
    main()
