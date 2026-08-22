#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dpc.py — pure-Python reader for Asobo "Zouna" .DPC BigFiles, REQUIEM generation.

Ported 1:1 from amrshaheen61/APT_DPC_Tool (Core/DpcHelper.cs, the authoritative
Plague Tale parser). Requiem specifics (differ from Innocence!):
  * offsets are stored in 16-BYTE units  (FixedOffset = value << 4)
  * object payloads are ZLIB-compressed  (Ionic.Zlib == stdlib zlib; the game
    ships zlib.dll) — NOT LZ4 (LZ4 is the Innocence/MSFS path)
  * header = banner[257] + i32 unknown(=3) + i32*16 {blockDescOffset, filesBlockSize,
    filesBlockOffset, mapSize, mapOffset}

Object payload layout (at a file's Offset):
  u64 Type | u64 ID | i64 (pad) | i32 BufferSize | i32 InfoBufferSize | i32 OriginalSize
  | i32 CompressSize(-8) | i16 Padding | u8 IsCompressed
  if IsCompressed==0: BufferSize raw bytes  (the whole object, uncompressed)
  else: InfoBufferSize "info" bytes, then i32 _uncompSize, i32 _compSize, then
        (BufferSize-InfoBufferSize-8-Padding) zlib bytes -> OriginalSize decompressed

So a decoded object = [info bytes] + [decompressed body].  Known class hashes:
  Texture = 0xE9659CD1C3F3326D · FontMap = 0x87218B06F6FE91FD · Script = 0x1E1E2446DCB3072A
"""

from __future__ import annotations

import os
import struct
import sys
import zlib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLASS_NAMES = {
    0xE9659CD1C3F3326D: "Texture",
    0x87218B06F6FE91FD: "FontMap",
    0x1E1E2446DCB3072A: "Script",
}


class R:
    """little-endian cursor reader"""
    def __init__(self, data: bytes, pos: int = 0):
        self.d = data
        self.p = pos

    def seek(self, p): self.p = p
    def skip(self, n): self.p += n
    def bytes(self, n):
        b = self.d[self.p:self.p + n]; self.p += n; return b
    def u8(self):  v = self.d[self.p]; self.p += 1; return v
    def i16(self): v = struct.unpack_from("<h", self.d, self.p)[0]; self.p += 2; return v
    def i32(self): v = struct.unpack_from("<i", self.d, self.p)[0]; self.p += 4; return v
    def u32(self): v = struct.unpack_from("<I", self.d, self.p)[0]; self.p += 4; return v
    def i64(self): v = struct.unpack_from("<q", self.d, self.p)[0]; self.p += 8; return v
    def u64(self): v = struct.unpack_from("<Q", self.d, self.p)[0]; self.p += 8; return v


FX = 4  # Requiem shift: offset units are 16 bytes


class FileEntry:
    __slots__ = ("id", "ftype", "offset", "csize", "usize", "map_pos")

    def __init__(self, id, ftype, offset, csize, usize, map_pos):
        self.id, self.ftype, self.offset = id, ftype, offset
        self.csize, self.usize, self.map_pos = csize, usize, map_pos

    @property
    def cls(self):
        return CLASS_NAMES.get(self.ftype, f"{self.ftype:016X}")

    def __repr__(self):
        return (f"FileEntry(id={self.id:016X} cls={self.cls} off={self.offset} "
                f"csize={self.csize} usize={self.usize})")


class Dpc:
    def __init__(self, path: str):
        self.path = path
        self.data = open(path, "rb").read()
        self._parse()

    def _parse(self):
        r = R(self.data)
        r.skip(257)                         # version banner
        self.unknown = r.i32()              # == 3
        self.block_desc_off = r.i32() << FX
        self.files_block_size = r.i32() << FX
        self.files_block_off = r.i32() << FX
        self.map_size = r.i32() << FX
        self.map_off = r.i32() << FX

        self.files: list[FileEntry] = []
        if self.block_desc_off:
            self._read_blocks()
        # (map-only path, used when files live in COMMON.DPC — not the FONT case)

    def _read_blocks(self):
        r = R(self.data, self.block_desc_off)
        block_count = r.i32()
        blocks = []
        for _ in range(block_count):
            unk = r.bytes(24)                       # 8*3 "crc"
            files_map_off = r.i32() << FX
            data_files_off = files_map_off + (r.i32() << FX)
            blocks.append((unk, files_map_off, data_files_off))
        for unk, files_map_off, data_files_off in blocks:
            self._read_files_map(files_map_off)

    def _read_files_map(self, files_map_off: int):
        r = R(self.data, files_map_off)
        blocks_count = r.i32()
        r.i32()                                     # block offset (data files)
        r.bytes(32)                                 # crc
        for _ in range(blocks_count):
            r.i32(); r.i64(); r.i64(); r.i64()      # data-block descs (files in COMMON path)
        # the FILE MAP proper begins at files_map_off + 1496
        r.seek(files_map_off + 1496)
        n = r.i32()
        for _ in range(n):
            self._read_file_entry(r)
        # Requiem tail: skip8, Num, skip16*Num, Num2, skip4*Num2, then a 2nd file list
        r.skip(8)
        num = r.i32(); r.skip(16 * num)
        num2 = r.i32(); r.skip(4 * num2)
        n2 = r.i32()
        for _ in range(n2):
            self._read_file_entry(r)

    def _read_file_entry(self, r: R):
        map_pos = r.p
        fid = r.u64()
        ftype = r.u64()
        offset = r.i32() << FX
        csize = r.i32()
        r.skip(8)                                   # unknown
        usize = r.i32()
        self.files.append(FileEntry(fid, ftype, offset, csize, usize, map_pos))

    # ------------------------------------------------------------------ #
    def read_object(self, fe: FileEntry) -> dict:
        """Decode one object at fe.offset -> {type,id,info,body,raw,is_compressed,...}."""
        r = R(self.data, fe.offset)
        otype = r.u64()
        oid = r.u64()
        r.i64()                                     # pad
        buffer_size = r.i32()
        info_size = r.i32()
        original_size = r.i32()
        comp_size_field = r.i32()                   # (= compressed+8)
        padding = r.i16()
        is_comp = r.u8()
        out = dict(type=otype, id=oid, buffer_size=buffer_size, info_size=info_size,
                   original_size=original_size, padding=padding, is_compressed=bool(is_comp),
                   header_end=r.p)
        if is_comp == 0:
            out["info"] = b""
            out["body"] = r.bytes(buffer_size)
        else:
            info = r.bytes(info_size)
            r.skip(padding)
            _u = r.i32(); _c = r.i32()
            comp_len = buffer_size - info_size - 8 - padding
            comp = r.bytes(comp_len)
            body = zlib.decompress(comp)
            out["info"] = info
            out["body"] = body
            out["_u"] = _u; out["_c"] = _c
        out["decoded"] = out["info"] + out["body"]
        return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("dpc", nargs="?",
                    default=r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC")
    ap.add_argument("--dump", help="dump decoded objects of this class (e.g. FontMap/Texture) to work/font/_dump/")
    args = ap.parse_args()

    d = Dpc(args.dpc)
    print(f"file: {args.dpc}  size={len(d.data)}")
    print(f"header: unknown={d.unknown} blockDescOff={d.block_desc_off} "
          f"filesBlockOff={d.files_block_off} filesBlockSize={d.files_block_size} "
          f"mapOff={d.map_off} mapSize={d.map_size}")
    print(f"files: {len(d.files)}")
    from collections import Counter
    cc = Counter(f.cls for f in d.files)
    print("by class:", dict(cc))
    print("\nfirst 25 entries:")
    for f in d.files[:25]:
        print("  ", f)

    if args.dump:
        outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_dump")
        os.makedirs(outdir, exist_ok=True)
        n = 0
        for f in d.files:
            if f.cls == args.dump:
                try:
                    o = d.read_object(f)
                except Exception as e:
                    print("  decode FAIL", f, e); continue
                fn = os.path.join(outdir, f"{f.id:016X}.{f.cls}.bin")
                open(fn, "wb").write(o["decoded"])
                print(f"  dumped {f.cls} id={f.id:016X} "
                      f"info={len(o['info'])} body={len(o['body'])} comp={o['is_compressed']}")
                n += 1
        print(f"dumped {n} {args.dump} objects to {outdir}")
