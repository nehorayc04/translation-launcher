#!/usr/bin/env python3
"""
mirage_font.py — inject the Hebrew block into AC Mirage's `FontFile` resources.

The menu proof (2026-07-22) rendered our Hebrew as tofu while the Latin marker
`ZZ-P-C` rendered fine, so the text pipeline is proven and the FONT is the gate.
A full-forge content scan found the fonts as class **`FontFile`**
(`zlib.crc32("FontFile") == 3295364632`) — 9 of them, all in `DataPC.forge`
(the patch forge has none, so the base copy is the one that renders).

FontFile object layout (delta-13, constant across all 9):
    +0   u32 class_hash  = 3295364632
    +4   i32 size        = len(content) - 13
    +8   i32 name_len    = 0            (fonts carry no name)
    +12  u8  0x00        (name terminator)
    +13  u8  0x01        (file header byte)
    +14  u64 ClassID     (== the forge resource id)
    +22  u32 Hash        (== class_hash)
    +26  i32 ttf_len     <-- LENGTH FIELD #2
    +30  sfnt bytes

Shipped faces (measured): DINPro Regular / DINPro-Bold carry the Arabic (42/48) and
are what the menu draws with; Portrait Cy Regular/Bold are the display face; two big
DINPro are the CJK-heavy fallbacks; "ACK Younger Futhark" is a runic prop font.
**All nine have 0/27 Hebrew.** Donor = Heebo (designed as the Hebrew companion to
Roboto, the closest match to DIN's geometric sans).

    python mirage_font.py <forge> list
    python mirage_font.py <forge> inject <out_dir> [--donor path] [--all]
"""
import argparse
import io
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "acshadows", "tools"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "anno1800", "work"))

from mirage_forge import Forge  # noqa: E402
import acs_cfd  # noqa: E402
from anno_font import _add_hebrew  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FONT_CLASS = 3295364632
TTF_OFF = 30
LEN_OFF = 26
HEADER_DELTA = 13
DEFAULT_DONOR = os.path.join(HERE, "..", "..", "spiderman2", "extracted", "_heebo",
                             "Heebo-Regular.ttf")
DEFAULT_DONOR_BOLD = os.path.join(HERE, "..", "..", "spiderman2", "extracted", "_heebo",
                                  "Heebo-Bold.ttf")
HEB = range(0x05D0, 0x05EB)


def font_entries(fg):
    return [e for e in fg.entries if e.id >> 60]        # font ids have the high nibble set


class FontRes:
    def __init__(self, blob, oodle):
        self.oodle = oodle
        self.cfds, consumed = acs_cfd.decode_resource(blob, oodle)
        self.trailer = blob[consumed:]
        self.content = self.cfds[-1][0]
        c = self.content
        self.cls, self.size_field, self.name_len = struct.unpack_from("<Iii", c, 0)
        self.ttf_len = struct.unpack_from("<i", c, LEN_OFF)[0]
        self.ttf = c[TTF_OFF:TTF_OFF + self.ttf_len]
        self.header_delta = len(c) - self.size_field

    def rebuild(self, ttf):
        new_content = bytearray(self.content[:LEN_OFF])
        new_content += struct.pack("<i", len(ttf))
        new_content += ttf
        struct.pack_into("<i", new_content, 4, len(new_content) - self.header_delta)
        out = bytearray()
        for i, (data, cinfo) in enumerate(self.cfds):
            out += acs_cfd.build_cfd(bytes(new_content) if i == len(self.cfds) - 1 else data,
                                     cinfo, self.oodle)
        out += self.trailer
        return bytes(out)


def describe(ttf):
    try:
        f = TTFont(io.BytesIO(ttf), lazy=True, fontNumber=0)
        cm = set()
        for t in f["cmap"].tables:
            try:
                cm |= set(t.cmap.keys())
            except Exception:
                pass
        name = ""
        try:
            name = f["name"].getDebugName(4) or f["name"].getDebugName(1) or ""
        except Exception:
            pass
        return {
            "name": name,
            "glyphs": f["maxp"].numGlyphs,
            "lat": sum(1 for c in range(0x41, 0x5B) if c in cm),
            "ara": sum(1 for c in range(0x0620, 0x0650) if c in cm),
            "heb": sum(1 for c in HEB if c in cm),
            "cff": "CFF " in f,
        }
    except Exception as ex:
        return {"name": f"<parse fail: {type(ex).__name__}>", "glyphs": 0,
                "lat": 0, "ara": 0, "heb": 0, "cff": False}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forge")
    ap.add_argument("cmd", choices=["list", "inject"])
    ap.add_argument("out", nargs="?")
    ap.add_argument("--donor", default=DEFAULT_DONOR)
    ap.add_argument("--donor-bold", default=DEFAULT_DONOR_BOLD)
    a = ap.parse_args()

    fg = Forge(a.forge)
    od = acs_cfd._oodle()
    ents = font_entries(fg)
    print(f"# {len(ents)} FontFile candidates in {os.path.basename(a.forge)}")

    if a.cmd == "inject":
        os.makedirs(a.out, exist_ok=True)
        donor = TTFont(a.donor)
        donor_b = TTFont(a.donor_bold) if os.path.exists(a.donor_bold) else donor

    for e in ents:
        try:
            fr = FontRes(fg.read(e), od)
        except Exception as ex:
            print(f"  id={e.id} SKIP ({type(ex).__name__})")
            continue
        if fr.cls != FONT_CLASS:
            continue
        info = describe(fr.ttf)
        tag = (f"  id={e.id} ttf={fr.ttf_len:>10,} glyphs={info['glyphs']:>6} "
               f"LAT={info['lat']}/26 ARA={info['ara']}/48 HEB={info['heb']}/27  {info['name']}")
        if a.cmd == "list":
            print(tag)
            continue

        print(tag)
        try:
            f = TTFont(io.BytesIO(fr.ttf), fontNumber=0)
            src = donor_b if "bold" in (info["name"] or "").lower() else donor
            added, skipped = _add_hebrew(f, src)
            buf = io.BytesIO()
            f.save(buf)
            new_ttf = buf.getvalue()
            chk = describe(new_ttf)
            blob = fr.rebuild(new_ttf)
            p = os.path.join(a.out, f"{e.id}.bin")
            open(p, "wb").write(blob)
            print(f"      -> +{added} glyphs (skipped {skipped})  HEB now {chk['heb']}/27  "
                  f"LAT {chk['lat']}/26 ARA {chk['ara']}/48  ttf {fr.ttf_len:,}->{len(new_ttf):,}  "
                  f"blob {len(blob):,} B  {os.path.basename(p)}")
        except Exception as ex:
            print(f"      -> INJECT FAILED: {type(ex).__name__}: {ex}")


if __name__ == "__main__":
    main()
