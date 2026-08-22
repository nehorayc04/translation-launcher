#!/usr/bin/env python3
"""
mirage_texture.py — swap the pixel payload of an AC Mirage `TextureMap` resource.

Used to put the Hebrew title logo in place of the shipped Arabic one
(`UI_TitleReveal_AR_Map_PC_Ggp_Prospero_Scarlett` in `DataPC_extra.forge`).

🔴 A TITLE TEXTURE EXISTS AS **TWO** RESOURCES AND BOTH MUST BE PATCHED:
    UI_TitleReveal_AR_Map_PC_...  class TextureMap     (2729961751)  header 264 B
    UI_TitleReveal_AR_MapDesc     class TextureMapSpec (2560476850)  header 325 B
Both carry a FULL 643,200-byte BC7 payload of the same image. Patching only the
`_Map_PC_` one changes nothing on screen — the shipped logo kept rendering from the
`_MapDesc` copy. The "Desc" name reads like a descriptor and is not: it is the pixels
too. So the header length is DERIVED (`len(content) - len(payload)`) instead of
hardcoded, and both classes are accepted.

Object layout, measured on the real resources:
    +0    u32 class_hash
    +4    i32 size       = len(content) - (12 + name_len + 1)
    +8    i32 name_len
    +12   char[name_len] name + NUL
          ... texture descriptor ...
    +N    the BC7 payload, 643,200 B for this 1072x600 slot

The replacement is the SAME length as the original, so the `size` field and every
other header byte are carried over untouched — a delta-0 content swap, the cleanest
case there is. Only the pixel bytes after the header change.

    python mirage_texture.py <forge> info  <resource_id>
    python mirage_texture.py <forge> build <resource_id> <payload.bc7> <out.bin>
    python mirage_texture.py <forge> findall <substring>
"""
import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "acshadows", "tools"))

from mirage_forge import Forge  # noqa: E402
import acs_cfd  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TEX_CLASSES = {2729961751: "TextureMap", 2560476850: "TextureMapSpec"}


class TextureRes:
    def __init__(self, blob, oodle, payload_len=None):
        self.oodle = oodle
        self.cfds, consumed = acs_cfd.decode_resource(blob, oodle)
        self.trailer = blob[consumed:]
        self.content = self.cfds[-1][0]
        c = self.content
        self.cls, self.size_field, self.name_len = struct.unpack_from("<Iii", c, 0)
        if self.cls not in TEX_CLASSES:
            raise SystemExit(f"class {self.cls} is not a texture "
                             f"({'/'.join(TEX_CLASSES.values())})")
        self.cls_name = TEX_CLASSES[self.cls]
        self.name = c[12:12 + self.name_len].decode("utf-8", "replace")
        # The header length differs per class (264 for TextureMap, 325 for
        # TextureMapSpec), so it is derived from the payload rather than hardcoded.
        self.pixel_off = (len(c) - payload_len) if payload_len else self._guess_off()
        self.header = c[:self.pixel_off]
        self.pixels = c[self.pixel_off:]
        self.header_delta = len(c) - self.size_field

    def _guess_off(self):
        """Without a stated payload size, assume the slot is whatever follows the
        largest plausible header — for these resources that is 264 or 325."""
        for off in (264, 325):
            n = len(self.content) - off
            if n > 0 and n % 16 == 0:
                return off
        raise SystemExit("cannot locate the pixel payload; pass its length explicitly")

    def rebuild(self, pixels):
        if len(pixels) != len(self.pixels):
            raise SystemExit(f"payload {len(pixels):,} != slot {len(self.pixels):,} — "
                             f"this swap is delta-0 by design")
        new_content = self.header + pixels
        # length is unchanged, so the size field must come out identical; assert it
        # rather than recompute blindly, so a layout surprise is caught here
        assert len(new_content) - self.header_delta == self.size_field
        out = bytearray()
        for i, (data, cinfo) in enumerate(self.cfds):
            out += acs_cfd.build_cfd(new_content if i == len(self.cfds) - 1 else data,
                                     cinfo, self.oodle)
        out += self.trailer
        return bytes(out)


def load(forge, res_id, oodle=None, payload_len=None):
    fg = Forge(forge)
    od = oodle or acs_cfd._oodle()
    m = [e for e in fg.entries if e.id == int(res_id)]
    if not m:
        raise SystemExit(f"resource id {res_id} not found")
    blob = fg.read(m[0])
    fg.f.close()
    return TextureRes(blob, od, payload_len), len(blob)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forge")
    ap.add_argument("cmd", choices=["info", "build"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()

    plen = os.path.getsize(a.args[1]) if a.cmd == "build" else None
    res, blob_len = load(a.forge, a.args[0], payload_len=plen)
    print(f"# {res.name}  [{res.cls_name}]")
    print(f"# content={len(res.content):,}  header={res.pixel_off}  "
          f"pixels={len(res.pixels):,}  size_field={res.size_field:,}  "
          f"cfds={len(res.cfds)}  on-disk={blob_len:,}")
    if a.cmd == "info":
        return 0

    pixels = open(a.args[1], "rb").read()
    blob = res.rebuild(pixels)
    open(a.args[2], "wb").write(blob)

    # read it straight back through the decoder — the only check that proves the
    # re-encode is loadable, rather than merely that it was written
    back = TextureRes(blob, res.oodle, len(pixels))
    same_hdr = back.header == res.header
    same_px = back.pixels == pixels
    print(f"  re-decode: header {'IDENTICAL' if same_hdr else 'CHANGED'} · "
          f"pixels {'MATCH' if same_px else 'MISMATCH'} · "
          f"size_field {back.size_field:,}")
    print(f"  -> {os.path.basename(a.args[2])}  {len(blob):,} B "
          f"(was {blob_len:,} on disk)")
    return 0 if (same_hdr and same_px) else 1


if __name__ == "__main__":
    sys.exit(main())
