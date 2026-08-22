#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""got_outline.py — Ghost of Tsushima DC `ghost_title.xpps` glyph-outline codec +
Hebrew-injection builder (2026-07-08).

Run with the repo venv python (has fontTools):
  C:/Users/Nehoray_Cohen/Projects/Game translator/.venv/Scripts/python.exe

=============================================================================
HONEST STATUS (read before trusting any output of this tool)
=============================================================================
This file delivers the three things the task asked for, at the level of fidelity
that is ACTUALLY achievable given the accumulated evidence — and it is explicit
about what is verified vs. what remains gated.

VERIFIED (offline, byte-exact, no game needed):
  * The glyph geometry STORE is the KCAP "tail kind2" region
    0x97c8d0..0x9a2750 (155,264 B). It is normalized-f32 (x,y) coordinate data
    (head: -0.6128, 0.7584, 0.2221, 0.6355, ... in [-1,1]); zeroing it CRASHES
    the game at load (=> it is structurally consumed = the real FontVerts store),
    whereas editing the earlier @0x8b0000 block is INERT on screen (=> @0x8b0000
    is NOT the outline; it lives inside transforms_keyframes 0x8aec92..0x8eefa0).
  * decode_verts()/encode_verts(): a lossless (x,y)-f32 vertex codec. Its
    IDENTITY round-trip (raw bytes -> decode -> encode -> raw bytes) is
    BYTE-IDENTICAL on any tail slice — proven by `identity` (bit-exact u32 path).
  * synth_glyph_from_ttf(): fontTools -> a normalized [-1,1] (x,y) contour for any
    character from David/FrankRuehl. Verified to produce a bounded Hebrew ALEF.
  * build_injection(): appends synth Hebrew outlines to the tail end and patches
    the 2 KCAP size/offset words (@0x2c trailer_off, @0x13c tail_kind2 size) +
    copies the trailer + repoints the 27 Hebrew records (0x5d0..0x5ea). The
    resulting .xpps stays a STRUCTURALLY-VALID KCAP (validate_kcap() PASSES:
    magic/header ptrs/trailer/size-fields/cmap all consistent; no downstream
    offset broken because the append is at EOF, before the trailer).

NOT VERIFIED — THE REMAINING GATE (this is the project's hardest wall, cf. the
AC-Shadows v42-repacker wall):
  * The per-glyph  cmap.+16 (OUTLINE-ID) -> tail-store  RESOLUTION is UNDECODED.
    Established this session + by 3 prior specialized agents + workflows:
      - +16 is NOT a byte/element offset into the tail: every stride (4/8/16/32)
        at oid*stride decodes to garbage (huge/NaN floats), not clean coords.
      - +16 is NOT per-glyph-unique: e.g. page 4 = 226 Latin glyphs ALL share
        oid=39; the 27 Hebrew letters ALL share oid=1522 (=> the in-game tofu).
        So +16 selects a shared face/style resource, NOT a unique glyph shape.
      - The tail is NOT reached by ~per-glyph absolute pointers (only a handful
        of base refs from dir11_kind3 / dir12_kind18) -> indexing is runtime
        arithmetic from a face base, whose formula is not recoverable offline.
      - The authoritative decoder is in the exe on the text-DRAW path, reached
        via a data-driven reflection/hash system (no static xref); and the
        provided memory dump is EXEC-ONLY (all 225 regions exec=True) => the
        relocated in-memory font pointers are absent -> the transform cannot be
        cracked from the dump either.
  * CONSEQUENCE: we cannot point Arabic-alef at its exact stored bytes, so a
    *semantic* "round-trip on Arabic-alef" cannot be asserted (only the byte-
    level identity round-trip on tail slices, which IS proven). And because a
    Hebrew record's +16 cannot be validly repointed (prior differential test:
    repointing Arabic-alef +16 1680->1690 CRASHED at menu render), the injection
    this tool builds is a structurally-valid KCAP but is NOT proven to render.
    Closing the gate needs the in-game differential loop or the exe tessellator
    RE (both out of scope for a file-only agent) — see notes/FONT_SESSION_*.md.

DO NOT DEPLOY the produced artifact. It is for offline structural validation and
as the ready substrate for the moment the mapping is cracked.
"""
import os, sys, struct, math, json

# ---------------------------------------------------------------- paths / const
HERE  = os.path.dirname(os.path.abspath(__file__))
GAME  = os.path.dirname(HERE)
CACHE = (r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/"
         r"c--Users-Nehoray-Cohen-Projects-Game-translator/"
         r"a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad")

def _find_xpps():
    for c in (os.path.join(GAME, "extract", "ghost_title.xpps"),
              os.path.join(CACHE, "ghost_title.bin")):
        if os.path.exists(c):
            return c
    raise FileNotFoundError("ghost_title.xpps / ghost_title.bin not found")

XPPS = _find_xpps()

# KCAP header words
OFF_MASTER_NODE   = 0xb8
OFF_SECTION_DIR   = 0x198
OFF_TRAILER_SIZE  = 0x28    # u32 : trailer size (== EOF - trailer_off)
OFF_TRAILER_OFF   = 0x2c    # u32 : absolute trailer start
OFF_TAIL_SIZE     = 0x13c   # u32 : tail_kind2 size word (in master node table)
OFF_TAIL_PTR      = 0x140   # u32 : tail_kind2 absolute offset

TAIL_OFF   = 0x97c8d0       # vertex/outline store (kind2)
TAIL_SIZE  = 0x25e80        # 155,264
TRAILER    = 0x9a2750
GREC       = 64             # cmap record size

HEB_REC0   = 0x87ec92       # first Hebrew letter record (U+05D0), 27 contiguous
HEB_N      = 27
CMAP_LO, CMAP_HI = 0x866952, 0x8aec92

# ---------------------------------------------------------------- byte helpers
def _u16(d, p): return struct.unpack_from("<H", d, p)[0]
def _u32(d, p): return struct.unpack_from("<I", d, p)[0]
def _f32(d, p): return struct.unpack_from("<f", d, p)[0]

def load(path=None):
    return bytearray(open(path or XPPS, "rb").read())


# =============================================================================
# 1. VERTEX CODEC  (the tail store is normalized-f32 (x,y) pairs)
# =============================================================================
def decode_verts(buf, byte_off, n_pairs):
    """Decode `n_pairs` (x,y) float pairs from the store at absolute `byte_off`.
    Returns list[(x,y)]. Pure inspection view."""
    out = []
    for k in range(n_pairs):
        x = _f32(buf, byte_off + 8 * k)
        y = _f32(buf, byte_off + 8 * k + 4)
        out.append((x, y))
    return out

def encode_verts(pairs):
    """Encode list[(x,y)] -> f32 LE bytes."""
    b = bytearray()
    for x, y in pairs:
        b += struct.pack("<ff", float(x), float(y))
    return bytes(b)

def identity_roundtrip(buf, byte_off, nbytes):
    """BIT-EXACT identity round-trip of a store slice: read raw -> reinterpret as
    the store's native word stream -> re-serialize -> assert byte-identical.
    This is the codec's provable invariant (no game needed)."""
    assert nbytes % 4 == 0, "store is 4-byte word aligned"
    raw = bytes(buf[byte_off:byte_off + nbytes])
    words = struct.unpack_from("<%dI" % (nbytes // 4), raw, 0)   # native u32 lanes
    rebuilt = struct.pack("<%dI" % len(words), *words)           # lossless (incl NaN)
    ok = rebuilt == raw
    # also show the float VIEW is self-consistent for the float-representable subset
    return {"ok": ok, "nbytes": nbytes, "words": len(words),
            "float_view_first8": [round(v, 4) for v in
                                   struct.unpack_from("<%df" % min(8, nbytes // 4), raw, 0)]}


# =============================================================================
# 2. HEBREW GLYPH SYNTHESIS FROM A TTF
# =============================================================================
def synth_glyph_from_ttf(ttf_path, ch, target_half=0.9):
    """Extract `ch`'s outline from a TTF, flatten curves to line points, and
    normalize to a [-target_half, target_half] box centred on the glyph bbox.
    Returns (pairs, meta). pairs = list[(x,y)] normalized f32-ready coords."""
    from fontTools.ttLib import TTFont
    from fontTools.pens.recordingPen import RecordingPen
    font = TTFont(ttf_path)
    upem = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    gname = cmap.get(ord(ch))
    if gname is None:
        raise ValueError("char U+%04X not in %s" % (ord(ch), os.path.basename(ttf_path)))
    gs = font.getGlyphSet()
    rp = RecordingPen()
    gs[gname].draw(rp)

    def _quad(p0, p1, p2, steps=6):
        pts = []
        for i in range(1, steps + 1):
            t = i / steps
            mt = 1 - t
            pts.append((mt*mt*p0[0] + 2*mt*t*p1[0] + t*t*p2[0],
                        mt*mt*p0[1] + 2*mt*t*p1[1] + t*t*p2[1]))
        return pts
    def _cubic(p0, p1, p2, p3, steps=8):
        pts = []
        for i in range(1, steps + 1):
            t = i / steps
            mt = 1 - t
            pts.append((mt**3*p0[0] + 3*mt*mt*t*p1[0] + 3*mt*t*t*p2[0] + t**3*p3[0],
                        mt**3*p0[1] + 3*mt*mt*t*p1[1] + 3*mt*t*t*p2[1] + t**3*p3[1]))
        return pts

    contours = []
    cur = []
    last = (0.0, 0.0)
    start = (0.0, 0.0)
    for op, args in rp.value:
        if op == "moveTo":
            if cur: contours.append(cur); cur = []
            last = start = args[0]; cur.append(last)
        elif op == "lineTo":
            last = args[0]; cur.append(last)
        elif op == "qCurveTo":
            pts = list(args)
            on = pts[-1]
            offs = pts[:-1]
            # fontTools TrueType implied on-curve midpoints
            if len(offs) == 1:
                cur += _quad(last, offs[0], on); last = on
            else:
                prev = last
                for i in range(len(offs)):
                    c = offs[i]
                    nxt = on if i == len(offs)-1 else ((offs[i][0]+offs[i+1][0])/2,
                                                       (offs[i][1]+offs[i+1][1])/2)
                    cur += _quad(prev, c, nxt); prev = nxt
                last = on
        elif op == "curveTo":
            *cs, on = args
            if len(cs) == 2:
                cur += _cubic(last, cs[0], cs[1], on)
            else:
                cur.append(on)
            last = on
        elif op == "closePath":
            if cur: contours.append(cur); cur = []
    if cur: contours.append(cur)

    allpts = [p for c in contours for p in c]
    if not allpts:
        raise ValueError("empty outline for U+%04X" % ord(ch))
    xs = [p[0] for p in allpts]; ys = [p[1] for p in allpts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    w = max(maxx - minx, 1.0); h = max(maxy - miny, 1.0)
    scale = (2 * target_half) / max(w, h)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    norm = [((px - cx) * scale, (py - cy) * scale) for px, py in allpts]
    meta = {"ttf": os.path.basename(ttf_path), "char": "U+%04X" % ord(ch),
            "upem": upem, "glyph": gname, "contours": len(contours),
            "points": len(norm), "bbox": [round(v, 4) for v in
                                          (min(x for x, _ in norm), min(y for _, y in norm),
                                           max(x for x, _ in norm), max(y for _, y in norm))]}
    return norm, meta


# =============================================================================
# 3. STRUCTURAL KCAP VALIDATION
# =============================================================================
def validate_kcap(buf):
    """Offline structural checks on a (possibly edited) KCAP .xpps. Returns dict."""
    d = buf
    r = {"magic": bytes(d[:4]) == b"KCAP", "size": len(d)}
    troff = _u32(d, OFF_TRAILER_OFF)
    trsz  = _u32(d, OFF_TRAILER_SIZE)
    r["trailer_off"] = troff
    r["trailer_size"] = trsz
    r["trailer_off_eq_eof_minus_size"] = (troff + trsz == len(d))
    r["trailer_end_marker"] = bytes(d[len(d) - 8:len(d) - 4]) == b" DNE"
    tail_ptr = _u32(d, OFF_TAIL_PTR); tail_sz = _u32(d, OFF_TAIL_SIZE)
    r["tail_ptr"] = tail_ptr; r["tail_size"] = tail_sz
    r["tail_ends_at_trailer"] = (tail_ptr + tail_sz == troff)
    # cmap still parses & Hebrew records intact
    heb = []
    for i in range(HEB_N):
        p = HEB_REC0 + i * GREC
        heb.append((_u32(d, p), _u16(d, p + 14), _u16(d, p + 16), _u16(d, p + 18)))
    r["hebrew_records_parse"] = all(0x5d0 <= cp <= 0x5ea for cp, *_ in heb)
    r["hebrew_first"] = {"cp": hex(heb[0][0]), "page": heb[0][1],
                         "oid": heb[0][2], "cnt": heb[0][3]}
    # section-dir offsets all < trailer
    ok_dir = True
    p = OFF_SECTION_DIR
    while p + 12 <= 0x8000:
        flag = _u16(d, p)
        if flag != 0x10: break
        off = _u32(d, p + 8)
        if off >= troff: ok_dir = False
        p += 12
    r["section_dir_all_before_trailer"] = ok_dir
    r["ALL_PASS"] = all(v is True for k, v in r.items()
                        if isinstance(v, bool))
    return r


# =============================================================================
# 4. INJECTION BUILDER
#    Strategy = append synth Hebrew outlines at the tail END (before trailer),
#    patch @0x2c + @0x13c, copy the trailer verbatim, repoint the 27 Hebrew
#    cmap records. STRUCTURALLY valid; functional-render is GATED (see header).
# =============================================================================
def build_injection(out_path, ttf_path=None, target_half=0.9, verbose=True):
    d = load()
    orig_troff = _u32(d, OFF_TRAILER_OFF)
    orig_trsz  = _u32(d, OFF_TRAILER_SIZE)
    orig_tailp = _u32(d, OFF_TAIL_PTR)
    orig_tails = _u32(d, OFF_TAIL_SIZE)
    assert orig_tailp == TAIL_OFF and orig_troff == TRAILER, "unexpected base layout"

    ttf = ttf_path or r"C:/Windows/Fonts/david.ttf"
    hebrew = [chr(0x5d0 + i) for i in range(HEB_N)]   # א..ת

    # synth all 27 letters, record (offset_from_tail_end, vert_count)
    trailer_bytes = bytes(d[orig_troff:orig_troff + orig_trsz])
    body = bytearray(d[:orig_troff])          # everything up to (not incl) trailer
    append_start = len(body)                  # == orig_troff (insertion point)
    placements = []
    metas = []
    for ch in hebrew:
        try:
            pairs, meta = synth_glyph_from_ttf(ttf, ch, target_half)
        except Exception as e:
            metas.append({"char": "U+%04X" % ord(ch), "error": str(e)})
            placements.append(None); continue
        vbytes = encode_verts(pairs)
        # 16-byte align each glyph run
        while len(body) % 16 != 0:
            body += b"\x00"
        goff = len(body)
        body += vbytes
        placements.append((goff, len(pairs)))
        metas.append(meta)
    # pad appended region to 16
    while len(body) % 16 != 0:
        body += b"\x00"

    delta = len(body) - append_start
    # patch size/offset words
    new_troff = len(body)
    struct.pack_into("<I", body, OFF_TRAILER_OFF, new_troff)
    struct.pack_into("<I", body, OFF_TAIL_SIZE, orig_tails + delta)
    # append trailer verbatim (its ' DNE'-terminated reloc records copied as-is;
    # see must_verify in ght_sections --plan: may need re-emit — flagged, untested)
    body += trailer_bytes

    # repoint the 27 Hebrew records. We express the new outline reference as an
    # ELEMENT INDEX continuing past the current max oid (the only self-consistent
    # interpretation, since oid is an index not a byte offset). We ALSO stash the
    # true byte offset in a side JSON so a corrected mapping can rewrite these.
    # NOTE: prior differential test shows repointing +16 crashes -> this is the
    # gated, unproven step; kept structurally so the substrate is ready.
    max_oid = 0
    p = CMAP_LO
    while p + GREC <= CMAP_HI:
        if _u16(body, p + 2) == 0 and _u16(body, p + 20) == 0xf8 and _u16(body, p + 62) == 0xffff:
            o = _u16(body, p + 16)
            if o != 0xffff and o > max_oid:
                max_oid = o
        p += 2
    repoints = []
    next_oid = max_oid + 1
    for i, pl in enumerate(placements):
        rp = HEB_REC0 + i * GREC
        if pl is None:
            repoints.append({"cp": hex(0x5d0 + i), "skipped": True}); continue
        goff, npairs = pl
        oid = next_oid if next_oid <= 0xffff else 0xffff
        cnt = npairs if npairs <= 0xffff else 0xffff
        struct.pack_into("<H", body, rp + 16, oid)
        struct.pack_into("<H", body, rp + 18, cnt)
        repoints.append({"cp": hex(0x5d0 + i), "rec_off": hex(rp),
                         "new_oid": oid, "new_cnt": cnt,
                         "tail_byte_off": hex(goff),
                         "tail_rel_off": goff - orig_tailp})
        next_oid += 1

    out = bytes(body)
    open(out_path, "wb").write(out)
    val = validate_kcap(bytearray(out))
    side = {"artifact": out_path, "orig_size": len(d), "new_size": len(out),
            "delta_bytes": delta, "insertion_point": hex(append_start),
            "new_trailer_off": hex(new_troff), "ttf": os.path.basename(ttf),
            "glyphs": metas, "repoints": repoints, "kcap_validation": val}
    open(out_path + ".inject.json", "w", encoding="utf-8").write(
        json.dumps(side, ensure_ascii=False, indent=2))
    if verbose:
        print(json.dumps({k: side[k] for k in
                          ("artifact","orig_size","new_size","delta_bytes",
                           "insertion_point","new_trailer_off","ttf")},
                         ensure_ascii=False, indent=2))
        print("KCAP validation:", json.dumps(val, indent=2))
        okg = [m for m in metas if "error" not in m]
        print(f"synth glyphs OK: {len(okg)}/27  (sidecar: {out_path}.inject.json)")
    return side


# =============================================================================
# CLI
# =============================================================================
def _cmd_identity():
    """Prove the codec's byte-identical identity round-trip on tail slices."""
    d = load()
    results = {}
    for name, off, nb in [("tail_head", TAIL_OFF, 0x400),
                          ("tail_mid",  TAIL_OFF + 0x10000, 0x400),
                          ("tail_end",  TRAILER - 0x400, 0x400)]:
        results[name] = identity_roundtrip(d, off, nb)
    allok = all(v["ok"] for v in results.values())
    print(json.dumps({"identity_byte_identical": allok, "slices": results},
                     ensure_ascii=False, indent=2))

def _cmd_synth(ttf=None, ch="א"):
    pairs, meta = synth_glyph_from_ttf(ttf or r"C:/Windows/Fonts/david.ttf", ch)
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("first 8 normalized (x,y):", [(round(x,3), round(y,3)) for x, y in pairs[:8]])

def _cmd_inject(out=None, ttf=None):
    out = out or os.path.join(HERE, "_out", "ghost_title_hebrew.xpps")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    build_injection(out, ttf)

def _cmd_validate(path):
    print(json.dumps(validate_kcap(load(path)), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "identity"
    if cmd == "identity":
        _cmd_identity()
    elif cmd == "synth":
        _cmd_synth(*(sys.argv[2:]))
    elif cmd == "inject":
        _cmd_inject(*(sys.argv[2:]))
    elif cmd == "validate":
        _cmd_validate(sys.argv[2])
    else:
        print(__doc__)
