#!/usr/bin/env python3
r"""
aco_font.py — inject the Hebrew block into AC Odyssey's `FontFile` resources.

FontFile class = zlib.crc32("FontFile") = 3295364632. **15 of them, ALL in
`DataPC.forge`** (measured). Object layout is delta-13, byte-for-byte the same as
AC Mirage v29 — which is why that injector transfers unchanged:

    +0   u32 class_hash  = 3295364632
    +4   i32 size        = len(content) - 13        <-- LENGTH FIELD #1
    +8   i32 name_len    = 0            (fonts carry no name)
    +12  u8  0x00        (name terminator)
    +13  u8  0x01        (file header byte)
    +14  u64 ClassID     (== the forge resource id)
    +22  u32 Hash        (== class_hash)
    +26  i32 ttf_len                                <-- LENGTH FIELD #2
    +30  sfnt bytes

Shipped faces (cmap-measured, ALL 0/27 Hebrew):
    #1898 DINPro          511,232 B  1,936 glyphs  **37/43 Arabic**  <- the Arabic UI face
    #1891/1896/1900/1909/1913/1915/1917  DINPro variants (Latin/Cyrillic)
    #1893 DINCond-Medium · #1897 DINCond-Bold
    #1911 Friz Quadrata TT  (display/titles)
    #1901/#1903/#1905/#1907  big CJK fallbacks (DFPHeiW5-A, DFPHeiMedium-B5,
                              DFHSGothic-W5, MDChamGothicL_NC)

Donor = **Heebo** (the Hebrew companion to Roboto — closest geometric-sans match to
DIN, and the same donor that worked for Mirage's DINPro).

⚠️ [[font-inject-every-face]] — inject every face that can render UI text, not just
the Arabic one: partial injection makes SOME elements tofu. The 4 CJK fallbacks are
skipped by default (they are huge and never draw Latin/Hebrew UI).

    python aco_font.py <forge> list
    python aco_font.py <forge> inject <out_dir> [--donor PATH] [--all]
"""
import argparse
import io
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "anno1800", "work"))

import aco_forge                                      # noqa: E402
import aco_cfd                                        # noqa: E402
from anno_font import _add_hebrew                     # noqa: E402
from fontTools.ttLib import TTFont                    # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FONT_CLASS = 3295364632
TTF_OFF = 30
LEN_OFF = 26
HEADER_DELTA = 13

_HEEBO = os.path.join(HERE, "..", "..", "spiderman2", "extracted", "_heebo")
DEFAULT_DONOR = os.path.join(_HEEBO, "Heebo-Regular.ttf")
DEFAULT_DONOR_BOLD = os.path.join(_HEEBO, "Heebo-Bold.ttf")
DEFAULT_DONOR_MED = os.path.join(_HEEBO, "Heebo-Medium.ttf")

HEB = set(range(0x05D0, 0x05EB))
# huge CJK fallbacks — never draw Hebrew, skip unless --all
CJK_FACES = {"DFPHeiW5-A", "DFPHeiMedium-B5", "DFHSGothic-W5", "MDChamGothicL_NC"}


class FontRes:
    """One FontFile resource: decode -> mutate ttf -> rebuild both length fields."""

    def __init__(self, entry, blob, od):
        self.entry = entry
        self.parts = aco_cfd.decode_resource(blob, od)
        self.content = self.parts[-1][0]
        c = self.content
        self.cls, self.obj_size, self.name_len = struct.unpack_from("<Iii", c, 0)
        self.ttf_len = struct.unpack_from("<i", c, LEN_OFF)[0]
        self.ttf = c[TTF_OFF:TTF_OFF + self.ttf_len]

    def rebuild(self, ttf: bytes) -> bytes:
        """Splice a new TTF in and re-derive BOTH length fields."""
        out = bytearray(self.content[:TTF_OFF]) + ttf
        struct.pack_into("<i", out, LEN_OFF, len(ttf))          # field #2
        struct.pack_into("<i", out, 4, len(out) - HEADER_DELTA)  # field #1
        return bytes(out)

    def cfd_parts(self, ttf: bytes):
        """[(data, cinfo)] ready for aco_cfd.encode_resource."""
        parts = [(d, ci) for d, ci, _ in self.parts]
        parts[-1] = (self.rebuild(ttf), parts[-1][1])
        return parts

    @property
    def codec(self):
        return next((c for _, _, c in self.parts if c), aco_cfd.OODLE_KRAKEN)


def font_entries(fg, od):
    for e in fg.entries:
        try:
            blob = fg.read(e)
            if aco_cfd.peek_class(blob, od) != FONT_CLASS:
                continue
        except Exception:
            continue
        yield e, blob


def describe(ttf: bytes):
    f = TTFont(io.BytesIO(ttf), lazy=True, fontNumber=0)
    cm = set(f.getBestCmap().keys())
    name = ""
    for r in f["name"].names:
        if r.nameID == 4:
            name = r.toUnicode()
            break
    return name, len(cm), len(HEB & cm)


_DONOR_CACHE = {}


def donor_font(path):
    """Open (and cache) a donor as a TTFont — `_add_hebrew` needs an OPEN font,
    not a path."""
    if path not in _DONOR_CACHE:
        _DONOR_CACHE[path] = TTFont(path, fontNumber=0)
    return _DONOR_CACHE[path]


def pick_donor(face_name, a):
    n = (face_name or "").lower()
    if "bold" in n:
        return a.donor_bold
    if "medium" in n or "cond" in n:
        return a.donor_med
    return a.donor


def is_cff(ttf: bytes) -> bool:
    """OTTO / CFF outlines — `_add_hebrew` is a glyf-merge and is a NO-OP on these.
    A CFF face needs the TLOU1-style whole-font REPLACE instead."""
    return ttf[:4] == b"OTTO"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forge")
    ap.add_argument("cmd", choices=["list", "inject"])
    ap.add_argument("out", nargs="?")
    ap.add_argument("--donor", default=DEFAULT_DONOR)
    ap.add_argument("--donor-bold", default=DEFAULT_DONOR_BOLD)
    ap.add_argument("--donor-med", default=DEFAULT_DONOR_MED)
    ap.add_argument("--all", action="store_true", help="include the CJK fallbacks")
    a = ap.parse_args()

    fg = aco_forge.Forge(a.forge)
    od = aco_cfd.oodle()

    if a.cmd == "list":
        for e, blob in font_entries(fg, od):
            fr = FontRes(e, blob, od)
            nm, n, heb = describe(fr.ttf)
            print(f"  #{e.index:<5} id={e.id:<14} ttf={fr.ttf_len:>10,} "
                  f"glyphs={n:>6,} HEB={heb:>2}/27  {nm}")
        return 0

    os.makedirs(a.out, exist_ok=True)
    done = cff = 0
    for e, blob in font_entries(fg, od):
        fr = FontRes(e, blob, od)
        nm, _, heb = describe(fr.ttf)
        if not a.all and nm in CJK_FACES:
            print(f"  #{e.index:<5} {nm:<22} skipped (CJK fallback; use --all)")
            continue
        if is_cff(fr.ttf):
            cff += 1
            print(f"  #{e.index:<5} {nm:<22} SKIPPED — CFF/OTTO outlines: a glyf "
                  f"merge is a NO-OP here, this face needs a whole-font REPLACE")
            continue
        src = pick_donor(nm, a)
        f = TTFont(io.BytesIO(fr.ttf), fontNumber=0)
        added, skipped = _add_hebrew(f, donor_font(src))
        buf = io.BytesIO()
        f.save(buf)
        new_ttf = buf.getvalue()
        _, _, heb2 = describe(new_ttf)
        obj = fr.rebuild(new_ttf)
        res = aco_cfd.encode_resource(fr.cfd_parts(new_ttf),
                                      compressor=fr.codec, od=od)
        out = os.path.join(a.out, f"{e.id}.bin")
        open(out, "wb").write(res)
        print(f"  #{e.index:<5} {nm:<22} HEB {heb}->{heb2}/27 (+{added})  "
              f"ttf {fr.ttf_len:,}->{len(new_ttf):,}  "
              f"obj {len(fr.content):,}->{len(obj):,}  res={len(res):,} "
              f"(donor {os.path.basename(src)})")
        done += 1
    print(f"wrote {done} font resource blob(s) to {a.out}"
          + (f"   [{cff} CFF face(s) skipped]" if cff else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
