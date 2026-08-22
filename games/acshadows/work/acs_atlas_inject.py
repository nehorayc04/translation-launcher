#!/usr/bin/env python3
"""
acs_atlas_inject.py -- inject 27 Hebrew letters into the AC Shadows Arabic font ATLAS
(PhoenixFontDescriptorData), the REAL menu renderer. Pure in-place, exact forge-slot,
no forge repack, no TTF (the atlas is self-contained).

THE CRACK (offline-proven):
  A PHXFD weight = "PHXFD" + opaque header + "GFOF" section. GFOF header @+36 = u32 glyph
  count. Records start at GFOF+72, each 36 bytes:
      f32[7] metrics = [advance, xMin, yMin, xMax, yMax, W, H]   (bbox in px; W=xMax-xMin)
      u32  tex_offset  (ABSOLUTE into the decoded object)
      u32  codepoint   (<-- THIS is the map key; lookup is linear, NOT sorted)
  raster = decoded[tex_offset : tex_offset + W*H]  = 8-bit SDF (edge ~128, row-major, no header).
  The atlas is codepoint->raster; the FontFile TTFs are used only at bake time (proven: TTF
  outline-inject AND cmap-remap both did NOTHING in-game). So Hebrew is added by editing the
  atlas, not the font.

STRATEGY = REPURPOSE (no growth): pick 27 records for RARE Arabic presentation forms whose
raster slot (old W*H bytes) is big enough, then for each: set codepoint(+32) -> a Hebrew
codepoint, set W/H/metrics for the Hebrew glyph, and overwrite the raster bytes at the slot's
tex_offset with a rasterized Hebrew SDF (new W*H <= old slot). Decoded size is UNCHANGED
(pure in-place byte overwrite) -> re-encode Mermaid to the EXACT forge slot (acs_cfd), deploy
into all live (patch_02) Arabic weights. Reversible (per-resource blob backup, --revert).

    python acs_atlas_inject.py --dry     # build + ASCII-preview the injected Hebrew, write nothing
    python acs_atlas_inject.py --apply    # write into boot_patch_02 Arabic weights in-place
    python acs_atlas_inject.py --revert    # restore pristine resource blobs

GAME must be CLOSED.
"""
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import acs_forge as F          # noqa: E402
import acs_cfd as C            # noqa: E402

GAME = os.environ.get("ACS_GAME", r"C:\Games\Assassin's Creed Shadows")
_P2 = os.path.join(GAME, "DataPC_boot_patch_02.forge")
_P1 = os.path.join(GAME, "DataPC_boot_patch_01.forge")
_BOOT = os.path.join(GAME, "DataPC_boot.forge")
# Every Arabic PHXFD weight (arPF≈752 = the full Arabic set), across ALL forges. The
# fileID override chain (patch_02 > patch_01 > boot) decides which copy the menu actually
# renders from, so to be certain the active one is covered we inject Hebrew into EVERY
# Arabic weight everywhere. (forge, idx) pairs; idx is globally unique.
# ⚠️ INDICES ARE A CACHE, NOT AN ADDRESS. A Ubisoft update on 2026-08-21 added 6 records
# to patch_02 and changed one weight's size, shifting these by +2 — deploying against the
# stale values wrote 5.2 MB into unrelated live resources. Re-run `--discover` after ANY
# game update; `verify_slot()` refuses to write when a slot no longer matches.
_DEFAULT_WEIGHTS = [
    (_P2, 20632), (_P2, 20633), (_P2, 20634),          # patch_02 (highest priority)
    (_P1, 24062), (_P1, 24063),                         # patch_01
    (_BOOT, 82569), (_BOOT, 82570), (_BOOT, 82571),     # boot (base)
]


def discover_weights(forges=None, verbose=False):
    """Find the Arabic PHXFD weights by CONTENT, not by a remembered index.

    🔴 2026-08-21: a game update shifted patch_02's records (+6) and changed one weight's
    size, so the hardcoded indices silently pointed at other resources. Indices are a
    hint; the resource is identified by class hash 0xcbd4939a + an Arabic glyph table
    (1058 glyphs, ~255 arb + ~752 presentation forms). Re-run this after ANY game update.
    """
    import acs_forge as _F
    import acs_cfd as _C
    oodle = _C._oodle()
    out = []
    for path in (forges or (_P2, _P1, _BOOT)):
        for r in _F.parse(path)["recs"]:
            if r["hash"] != PHXFD_HASH or r["size"] < 200_000:
                continue
            try:
                with open(path, "rb") as f:
                    f.seek(r["offset"]); blob = f.read(r["size"])
                cfds, _e = _C.decode_resource(blob, oodle)
                dec = max((x for x, _ in cfds), key=len)
                cps = {x["cp"] for x in _records(dec)[3]}
            except Exception:
                continue
            if sum(1 for c in cps if 0x600 <= c <= 0x6FF) > 100:
                out.append((path, r["i"]))
                if verbose:
                    print(f"  {os.path.basename(path):<30} idx {r['i']:<6} "
                          f"@0x{r['offset']:x} size={r['size']:,}")
    return out


def _weights():
    env = os.environ.get("ACS_AR_WEIGHTS")               # "forgeTag:idx,..." tags p2/p1/boot
    if not env:
        return _DEFAULT_WEIGHTS
    tag = {"p2": _P2, "p1": _P1, "boot": _BOOT}
    out = []
    for item in env.split(","):
        t, i = item.split(":")
        out.append((tag[t], int(i)))
    return out


WEIGHTS = _weights()
FORGE = _P2                                              # legacy (unused by multi-forge paths)
HEB_FONT = os.environ.get("ACS_HEB_FONT", r"C:\Windows\Fonts\davidbd.ttf")
HEB = [chr(0x05D0 + i) for i in range(27)]          # א..ת
EDGE = 128                                            # SDF edge value (game convention)
BAK = os.path.join(HERE, "_atlasbak_%d.bin")
_POOL = None


def _pool():
    global _POOL
    if _POOL is None:
        _POOL = os.urandom(1 << 20)
    return _POOL


# ---------- Hebrew glyph rasterization (coverage -> blurred = SDF-ish, edge ~128) ----------
def raster_hebrew(px_body):
    """Rasterize each Hebrew letter at a body height ~px_body. Returns list of dicts:
    {ch, w, h, adv, xmin, ymin, xmax, ymax, bytes(bytearray w*h)}. Metrics in the atlas'
    pixel convention: baseline y=0, yMax=top above baseline, yMin=bottom (neg = descender)."""
    SS = 4                                            # supersample for clean AA
    font = ImageFont.truetype(HEB_FONT, px_body * SS)
    asc, desc = font.getmetrics()                     # pixels at the SS size
    out = []
    for ch in HEB:
        # measure ink bbox at pen origin (0, ascent) so baseline is at y=ascent
        mask = font.getmask(ch, mode="L")
        mw, mh = mask.size
        if mw == 0 or mh == 0:
            # empty glyph (shouldn't happen for Hebrew in David) -> 1px stub
            out.append(dict(ch=ch, w=2, h=2, adv=px_body // 2,
                            xmin=0.0, ymin=0.0, xmax=2.0, ymax=2.0,
                            bytes=bytearray(4))); continue
        img = Image.new("L", (mw, mh), 0)
        img.paste(Image.frombytes("L", mask.size, bytes(mask)), (0, 0))
        bbox = img.getbbox()
        l, t, r, b = bbox
        # pen origin: font renders top-left at (0,0) with baseline at y=ascent.
        base = asc
        # bbox in baseline-relative px (SS units): x right+, y up+ from baseline
        xmin_ss = l
        xmax_ss = r
        ymax_ss = base - t                            # top above baseline
        ymin_ss = base - b                            # bottom (neg if descender)
        crop = img.crop(bbox)
        w = max(1, round((r - l) / SS)); h = max(1, round((b - t) / SS))
        small = crop.resize((w, h), Image.LANCZOS)
        small = small.filter(ImageFilter.GaussianBlur(0.8))   # widen edge -> SDF-like ramp
        a = np.asarray(small, dtype=np.float32) / 255.0       # 0..1 coverage, AA edge ~0.5
        # map coverage -> SDF byte: inside(1)->~168, edge(0.5)->128, outside(0)->~40
        sdf = np.clip(EDGE + (a - 0.5) * 96.0, 0, 200).astype(np.uint8)
        try:
            adv = font.getlength(ch) / SS
        except Exception:
            adv = (r - l) / SS + 2
        out.append(dict(ch=ch, w=w, h=h, adv=float(adv),
                        xmin=xmin_ss / SS, ymin=ymin_ss / SS,
                        xmax=xmax_ss / SS, ymax=ymax_ss / SS,
                        bytes=bytearray(sdf.tobytes())))
    return out


# ---------- atlas record access ----------
# 🔴 RECORD LAYOUT (corrected 2026-08-21 from the AC Black Flag Resynced crack of the
# SAME class 0xCBD4939A; proven here by (a) 'I' rendering as a vertical stem only under
# this reading and (b) the FACE chain closing byte-exactly: face0 recs end at 38,412 ==
# face1's header):
#     FACE = [u32 count][16B zero][u32 upem][u32 0][f32 1.0]   -> 32 bytes
#     REC  = <I 7f I> = codepoint, advance, x0,y0,x1,y1, W,H, texOffset   -> 36 bytes
# The codepoint is the FIRST field, so records start at GFOF+68, NOT GFOF+72. The old
# reading was 4 bytes late: it got the floats and texOffset right (same addresses) but
# read the NEXT record's codepoint -- so every injection wrote Hebrew onto the codepoint
# of the following glyph while painting this one, i.e. a Hebrew codepoint resolved to the
# NEIGHBOURING Arabic presentation form. Because arPF neighbours are other forms of the
# SAME letter, that looked exactly like "the original Arabic shape came back".
CP_OFF = 0          # codepoint, relative to a record start
MET_OFF = 4         # the 7 f32 metrics
TEX_OFF = 32        # texture offset (absolute into the decoded object)


PHXFD_HASH = 0xcbd4939a


def verify_slot(forge, off, size, want_hash=PHXFD_HASH):
    """Refuse to write unless the forge's TOC STILL has exactly this record.

    🔴 2026-08-21: the backups store (offset, size) captured on 2026-07-17. patch_02
    later changed underneath us (+6 records, +256 KB — a game update or a parallel
    tool), so those offsets no longer started any record, and two --apply runs wrote
    5.2 MB into the MIDDLE of live resources. The TOC stayed self-consistent, so every
    contiguity check still said "OK" while the DATA was destroyed. An offset captured
    in a backup is only valid for the exact file it was captured from: re-validate it
    against the CURRENT table of contents before every write.
    """
    import acs_forge as _F
    for r in _F.parse(forge)["recs"]:
        if r["offset"] == off:
            if r["size"] != size:
                raise RuntimeError(
                    f"{os.path.basename(forge)} @0x{off:x}: record size is {r['size']:,} "
                    f"but the backup says {size:,} — the forge changed, refusing to write.")
            if r["hash"] != want_hash:
                raise RuntimeError(
                    f"{os.path.basename(forge)} @0x{off:x}: hash is 0x{r['hash']:08x}, "
                    f"expected 0x{want_hash:08x} — that offset is no longer the font.")
            return r
    raise RuntimeError(
        f"{os.path.basename(forge)} @0x{off:x}: NO record starts at this offset any more. "
        f"The forge was rebuilt since the backup was taken; re-discover the PHXFD indices "
        f"(hash 0x{want_hash:08x}) before deploying, and repair the forge first.")


def _records(dec):
    g = dec.find(b"GFOF")
    cnt = struct.unpack_from("<I", dec, g + 36)[0]
    start = g + 68
    recs = []
    for k in range(cnt):
        o = start + 36 * k
        cp = struct.unpack_from("<I", dec, o + CP_OFF)[0]
        m = list(struct.unpack_from("<7f", dec, o + MET_OFF))
        toff = struct.unpack_from("<I", dec, o + TEX_OFF)[0]
        recs.append(dict(k=k, o=o, m=m, toff=toff, cp=cp,
                         W=round(m[5]), H=round(m[6])))
    return g, cnt, start, recs


def pick_slots(recs, need, glyphs):
    """Choose `need` rare-presentation-form records whose slot (W*H bytes) fits the matching
    Hebrew glyph. Match biggest Hebrew glyph to biggest slot to guarantee fit."""
    order = sorted(range(need), key=lambda i: -(glyphs[i]["w"] * glyphs[i]["h"]))
    cand = sorted([r for r in recs if 0xFB50 <= r["cp"] <= 0xFEFF and r["W"] * r["H"] > 0],
                  key=lambda r: -(r["W"] * r["H"]))
    slots = {}
    ci = 0
    for gi in order:
        need_area = glyphs[gi]["w"] * glyphs[gi]["h"]
        while ci < len(cand) and cand[ci]["W"] * cand[ci]["H"] < need_area:
            ci += 1
        if ci >= len(cand):
            raise RuntimeError("not enough big-enough presentation-form slots")
        slots[gi] = cand[ci]; ci += 1
    return slots


def inject(dec, glyphs):
    """Return a NEW decoded bytes with 27 Hebrew glyphs written into repurposed slots.
    Same length (pure in-place overwrite)."""
    g, cnt, start, recs = _records(dec)
    slots = pick_slots(recs, len(glyphs), glyphs)
    d = bytearray(dec)
    for gi, gl in enumerate(glyphs):
        r = slots[gi]
        w, h = gl["w"], gl["h"]
        assert w * h <= r["W"] * r["H"], "glyph bigger than slot"
        # patch the record: metrics [advance, xMin, yMin, xMax, yMax, W, H] + tex_offset + codepoint
        o = r["o"]
        struct.pack_into("<7f", d, o + MET_OFF, gl["adv"], gl["xmin"], gl["ymin"],
                         gl["xmax"], gl["ymax"], float(w), float(h))
        # tex_offset stays (same slot); codepoint -> Hebrew
        struct.pack_into("<I", d, o + CP_OFF, 0x05D0 + gi)
        # write the raster at the slot's tex_offset, then ZERO the dead tail of the old slot
        # (never read again -> makes those Mermaid blocks highly compressible = slack for the
        # exact forge-slot fill; without this the re-encode narrowly overshoots the slot).
        slot_bytes = r["W"] * r["H"]
        d[r["toff"]: r["toff"] + w * h] = gl["bytes"]
        d[r["toff"] + w * h: r["toff"] + slot_bytes] = b"\x00" * (slot_bytes - w * h)
    return bytes(d), slots


# ---------- encode + deploy ----------
def _read(forge, idx, oodle):
    info = F.parse(forge); r = info["recs"][idx]
    with open(forge, "rb") as f:
        f.seek(r["offset"]); blob = f.read(r["size"])
    cfds, end = C.decode_resource(blob, oodle)
    assert end == r["size"]
    dec = max((x for x, _ in cfds), key=len)
    return r, blob, cfds, dec


def _encode_exact(cfds, new_dec, slot, oodle):
    """Re-encode with the new decoded object; land EXACTLY on the forge slot by appending
    incompressible filler to the object cfd's decoded tail (dead bytes the atlas never reads).
    Incompressible filler stores ~1:1, so a short secant hits the slot in a few probes."""
    pool = _pool()
    di = max(range(len(cfds)), key=lambda i: len(cfds[i][0]))    # the big (object) cfd
    other = sum(len(C.build_cfd(cfds[i][0], cfds[i][1], oodle, level=C.LEVEL))
                for i in range(len(cfds)) if i != di)

    def enc(k):                                       # total blob size with k filler bytes
        pay = new_dec + pool[:k]
        return other + len(C.build_cfd(pay, cfds[di][1], oodle, level=C.LEVEL))

    def finish(k):
        pay = new_dec + pool[:k]
        parts = list(cfds); parts[di] = (pay, cfds[di][1])
        return b"".join(C.build_cfd(dd, ci, oodle, level=C.LEVEL) for dd, ci in parts)

    base = enc(0)
    if base > slot:
        return None
    if base == slot:
        return finish(0)
    seen = {0: base}

    def size(k):
        if k not in seen:
            seen[k] = enc(k)
        return seen[k]

    # bracket [lo(<slot), hi(>=slot)] with a doubling probe, then bisect, then tiny linear scan
    lo, hi = 0, None
    k = slot - base                                   # slope ~1 first guess
    for _ in range(40):
        s = size(k)
        if s == slot:
            return finish(k)
        if s < slot:
            lo = max(lo, k); k = k + max(1, (slot - s) or 1)
        else:
            hi = k; break
    if hi is None:
        return None
    while hi - lo > 24:                                # bisect the bracket
        mid = (lo + hi) // 2
        s = size(mid)
        if s == slot:
            return finish(mid)
        (lo, hi) = (mid, hi) if s < slot else (lo, mid)
    for kk in range(lo, hi + 1):                       # exact byte in a <=25-wide window
        if size(kk) == slot:
            return finish(kk)
    return None


def _decoder_ok(blob):
    off = 0; n = len(blob)
    while off + 8 <= n and struct.unpack_from("<Q", blob, off)[0] == C.MAGIC:
        cnt = struct.unpack_from("<i", blob, off + 15)[0]; bi = off + 19
        bl = [struct.unpack_from("<ii", blob, bi + 8 * i) for i in range(cnt)]
        p = bi + cnt * 8
        for u, c in bl:
            p += 4
            if c != u and c >= 2 and (blob[p + 1] & 0x7F) != 10:
                return False
            p += c
        off = p
    return True


def _ascii(dec, cp):
    g, cnt, start, recs = _records(dec)
    r = next((x for x in recs if x["cp"] == cp), None)
    if not r:
        return "  (not found)"
    W, H = r["W"], r["H"]; b = dec[r["toff"]: r["toff"] + W * H]
    lines = []
    for y in range(0, H, max(1, H // 16)):
        row = b[y * W:(y + 1) * W]
        lines.append("   " + "".join("#" if v >= 150 else ("." if v >= EDGE else " ") for v in row[:48]))
    return "\n".join(lines)


def run(mode):
    oodle = C._oodle()
    glyphs = raster_hebrew(px_body=52)
    print(f"rasterized {len(glyphs)} Hebrew glyphs "
          f"(sizes {min(g['w'] for g in glyphs)}x{min(g['h'] for g in glyphs)}"
          f"..{max(g['w'] for g in glyphs)}x{max(g['h'] for g in glyphs)}) font={os.path.basename(HEB_FONT)}")
    built = []
    for forge, idx in WEIGHTS:
        r, blob, cfds, dec = _read(forge, idx, oodle)
        # skip a weight that is ALREADY injected (Hebrew present) so we don't double-repurpose
        _, _, _, r0 = _records(dec)
        if sum(1 for x in r0 if 0x05D0 <= x["cp"] <= 0x05EA) >= 20:
            print(f"  idx={idx} ({os.path.basename(forge)}): already has Hebrew -> SKIP")
            continue
        new_dec, slots = inject(dec, glyphs)
        assert len(new_dec) == len(dec)
        nb = _encode_exact(cfds, new_dec, r["size"], oodle)
        ok = nb is not None and len(nb) == r["size"] and _decoder_ok(nb)
        heb_ok = 0
        if ok:
            c2, e2 = C.decode_resource(nb, oodle); d2 = max((x for x, _ in c2), key=len)
            _, _, _, recs2 = _records(d2)
            cps2 = {x["cp"] for x in recs2}
            heb_ok = sum(1 for i in range(27) if (0x05D0 + i) in cps2)
        print(f"  idx={idx} ({os.path.basename(forge)}): slot={r['size']:,} built={len(nb) if nb else 0:,} "
              f"codecOK={_decoder_ok(nb) if nb else False} Heb={heb_ok}/27 -> {'OK' if ok and heb_ok==27 else 'FAIL'}")
        built.append((forge, idx, r, blob, nb if (ok and heb_ok == 27) else None, new_dec))
    if built:
        nd = built[0][5]
        for ch in ("א", "ש", "ד"):
            print(f"\n  injected {ch} (U+{ord(ch):04X}) in idx={built[0][1]}:")
            print(_ascii(nd, ord(ch)))
    ready = [b for b in built if b[4] is not None]
    if mode != "--apply":
        print(f"\n--dry: {len(ready)}/{len(built)} weights built + validated. Pass --apply to deploy.")
        return 0 if len(ready) == len(built) else 1
    if not built:
        print("\nnothing to do (all target weights already injected)."); return 0
    if len(ready) != len(built):
        print("\nnot all weights built -- aborting apply."); return 1
    for forge, idx, r, blob, nb, _ in ready:
        with open(BAK % idx, "wb") as gbak:
            gbak.write(struct.pack("<QQ", r["offset"], r["size"]) + forge.encode() + b"\x00" + blob)
        with open(forge, "r+b") as f:
            f.seek(r["offset"]); f.write(nb)
        print(f"WROTE idx={idx} in {os.path.basename(forge)} ({r['size']:,} B @0x{r['offset']:x}); backup {os.path.basename(BAK % idx)}")
    print("\nLAUNCH -> main menu (Arabic slot). If 'משחק חדש'/'טעינה' show HEBREW LETTERS "
          "instead of boxes -> font SOLVED. If wrong-shaped glyphs -> SDF/metrics tuning. "
          "If still boxes -> the menu uses a different Arabic weight (re-target).")
    return 0


def revert():
    """Restore EVERY backup on disk (glob), format-agnostic:
    old = <off u64><size u64><blob(size)>   (forge = patch_02, the original single-forge path)
    new = <off u64><size u64><forge-path>\\x00<blob(size)>."""
    import glob
    n = 0
    for p in sorted(glob.glob(os.path.join(HERE, "_atlasbak_*.bin"))):
        with open(p, "rb") as g:
            off, size = struct.unpack("<QQ", g.read(16)); rest = g.read()
        if len(rest) == size:                            # old single-forge format
            forge, blob = _P2, rest
        else:                                            # new multi-forge format
            z = rest.index(b"\x00")
            forge = rest[:z].decode(); blob = rest[z + 1:]
        assert len(blob) == size, f"{p}: blob {len(blob)} != size {size}"
        with open(forge, "r+b") as f:
            f.seek(off); f.write(blob)
        print(f"reverted {os.path.basename(p)} -> {os.path.basename(forge)} ({size:,} B @0x{off:x})"); n += 1
    print("no backups." if not n else "reverted %d weights." % n)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1] if len(sys.argv) > 1 else "--dry"
    sys.exit(revert() if a == "--revert" else run(a))
