"""Minimal SWF container reader/writer (FWS raw / CWS zlib) + tag walk.

Skyrim SE ships its Scaleform UI fonts as REAL SWF (not GFX/CFX):
    interface/fonts_en.swf       CWS v15  (zlib)
    interface/fonts_ru.swf       FWS v10  (raw)
    interface/fonts_console.swf  CWS v15
    interface/gfxfontlib.swf     CWS v10

Header: sig[3] + u8 version + u32 fileLength(UNCOMPRESSED total incl. the 8-byte head).
Body (after byte 8): RECT frameSize, u16 frameRate, u16 frameCount, then tags.
Tag: u16 (code<<6 | len); len==0x3F -> u32 longLength follows.

DefineFont2 = 48, DefineFont3 = 75, DefineFontInfo = 13, DefineFontInfo2 = 62,
DefineFontName = 88, DefineFontAlignZones = 73, ExportAssets = 56.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

DEFINE_FONT2 = 48
DEFINE_FONT3 = 75
DEFINE_FONT_NAME = 88
DEFINE_FONT_ALIGN_ZONES = 73
EXPORT_ASSETS = 56


@dataclass
class Tag:
    code: int
    body: bytes
    long_header: bool = False   # was it emitted with the 6-byte header?

    def pack(self) -> bytes:
        n = len(self.body)
        if n >= 0x3F or self.long_header:
            return struct.pack("<HI", (self.code << 6) | 0x3F, n) + self.body
        return struct.pack("<H", (self.code << 6) | n) + self.body


class Swf:
    def __init__(self, data: bytes):
        self.sig = data[:3]
        if self.sig not in (b"FWS", b"CWS", b"ZWS"):
            raise ValueError(f"not a SWF: {data[:4]!r}")
        self.version = data[3]
        self.declared_len = struct.unpack_from("<I", data, 4)[0]
        if self.sig == b"CWS":
            body = zlib.decompress(data[8:])
        elif self.sig == b"ZWS":
            raise ValueError("LZMA SWF not supported")
        else:
            body = data[8:]
        self.body = body
        # header block: RECT + frameRate + frameCount
        nbits = body[0] >> 3
        rect_bits = 5 + nbits * 4
        rect_bytes = (rect_bits + 7) // 8
        self.header = body[:rect_bytes + 4]
        p = rect_bytes + 4
        self.tags: list[Tag] = []
        while p < len(body):
            (th,) = struct.unpack_from("<H", body, p)
            p += 2
            code, ln = th >> 6, th & 0x3F
            long_hdr = ln == 0x3F
            if long_hdr:
                (ln,) = struct.unpack_from("<I", body, p)
                p += 4
            self.tags.append(Tag(code, body[p:p + ln], long_hdr))
            p += ln
            if code == 0:
                break

    def rebuild_body(self) -> bytes:
        return self.header + b"".join(t.pack() for t in self.tags)

    def pack(self, compress: bool | None = None) -> bytes:
        body = self.rebuild_body()
        total = 8 + len(body)
        if compress is None:
            compress = self.sig == b"CWS"
        sig = b"CWS" if compress else b"FWS"
        head = sig + bytes([self.version]) + struct.pack("<I", total)
        return head + (zlib.compress(body, 9) if compress else body)


def read(path) -> Swf:
    with open(path, "rb") as f:
        return Swf(f.read())
