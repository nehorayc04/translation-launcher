#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fonts_z.py — parse/edit a BIG_ARABIC Fonts_Z body (Requiem v2_128 generation).

Body layout (verified empirically against FONT/ENGLISH.DPC):
  u32 count
  count × Entry(40):  u32 CharacterID | u32 material_index | f32 advance
                      | f32 topX | f32 topY | f32 botX | f32 botY
                      | f32 bearX | f32 bearY | u32 (0)
  u32 material_count | material_count × u32  (Asobo32 name halves)
  <trailing bytes>   (a second name table / footer — preserved verbatim)

CharacterID: the char's UTF-8 bytes folded big-endian into a u32
  (e.g. 'A'=0x00000041; 'א' U+05D0 UTF-8 D7 90 -> 0x0000D790).
Atlas box (topX,topY)-(botX,botY) is in PIXELS within the page of material_index.
"""
from __future__ import annotations
import struct

STRIDE = 40


def char_to_cid(ch: str) -> int:
    b = ch.encode("utf-8")
    v = 0
    for byte in b:
        v = (v << 8) | byte
    return v


def cid_to_char(u: int) -> str:
    b = u.to_bytes(4, "big").lstrip(b"\x00") or b"\x00"
    try:
        return b.decode("utf-8")
    except Exception:
        return "?"


class Entry:
    __slots__ = ("cid", "mat", "adv", "x0", "y0", "x1", "y1", "bx", "by", "z")

    def __init__(self, raw: bytes):
        (self.cid, self.mat, self.adv, self.x0, self.y0,
         self.x1, self.y1, self.bx, self.by, self.z) = struct.unpack("<IIfffffffI", raw)

    def pack(self) -> bytes:
        return struct.pack("<IIfffffffI", self.cid, self.mat, self.adv, self.x0,
                           self.y0, self.x1, self.y1, self.bx, self.by, self.z)

    @property
    def char(self): return cid_to_char(self.cid)

    def copy(self):
        e = Entry.__new__(Entry)
        for s in self.__slots__:
            setattr(e, s, getattr(self, s))
        return e


class FontsZ:
    def __init__(self, body: bytes):
        self.count = struct.unpack_from("<I", body, 0)[0]
        self.entries = [Entry(body[4 + i * STRIDE: 4 + (i + 1) * STRIDE]) for i in range(self.count)]
        self.tail = body[4 + self.count * STRIDE:]   # material_names + footer, kept verbatim

    def by_char(self, ch: str):
        for e in self.entries:
            if e.char == ch:
                return e
        return None

    def build(self) -> bytes:
        out = struct.pack("<I", len(self.entries))
        for e in self.entries:
            out += e.pack()
        out += self.tail
        return out
