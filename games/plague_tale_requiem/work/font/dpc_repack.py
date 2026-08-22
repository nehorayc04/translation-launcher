#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dpc_repack.py — pure-Python REPACKER for Asobo Zouna Requiem-gen .DPC
(v2.128.52.19 / v2_128_52_19_pc). bff's `create` is unimplemented for this
generation and APT_DPC_Tool's import is broken, so we roll our own.

Strategy (identity-guaranteed): parse the file into regions, keep every untouched
object's ON-DISK bytes VERBATIM, re-lay the container, and patch only the offset/
size fields that move. A no-edit rebuild must be BYTE-IDENTICAL to the original —
that is the correctness proof before any real edit.

Layout of FONT/ENGLISH.DPC (single block):
  [0 .. 4096)              header (banner257 + i32=3 + 5×i32 offsets, ff-padded)
  [4096 .. datablk)        FilesMap: 1496-byte info (blocksCount,blockOffset,crc32,
                           data-block descriptors) + at +1496 the FileMap
                           (count + N FileBlock entries + Requiem tail + count2 + entries2)
  [datablk .. blocktbl)    data-block objects (sequential, zlib) + 0x00 pad
  [blocktbl .. fileblk)    block table (blockCount + per-block 24B unk + 2 i32 offs) + ff pad
  [fileblk .. EOF)         FileBlock objects (the 256x256 texture pages), 16-aligned, ff pad

All offsets in the header/tables are stored in 16-byte units (value<<4).
Object wrapper (at an object's byte offset):
  u64 type | u64 id | i64 pad | i32 bufSize | i32 infoSize | i32 origSize
  | i32 compField(=comp+8) | i16 padding | u8 isComp
  isComp!=0: info[infoSize] | pad[padding] | i32 _u | i32 _c | zlib[bufSize-infoSize-8-padding]
  isComp==0: raw[bufSize]
  on-disk object length = 43 + bufSize
"""

from __future__ import annotations
import os, struct, sys, zlib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ALIGN = 16
def align16(n: int) -> int: return (n + 15) & ~15


class Obj:
    __slots__ = ("otype", "oid", "info", "body", "is_comp", "raw", "dirty",
                 "unk16", "algo")
    def __init__(self, otype, oid, info, body, is_comp, raw, unk16=0, algo=0):
        self.otype, self.oid = otype, oid
        self.info, self.body = info, body
        self.is_comp = is_comp
        self.raw = raw          # original on-disk bytes (verbatim)
        self.dirty = False      # set True when body edited -> re-emit
        self.unk16 = unk16      # the i64 @+16 (real value: asset stamp/hash) — PRESERVE
        self.algo = algo        # the isCompressed byte value (4=zlib, 0=raw) — PRESERVE

    def emit(self) -> bytes:
        if not self.dirty:
            return self.raw
        info = self.info; body = self.body
        if self.is_comp:
            comp = zlib.compress(body, 9)
            info_sz, comp_len = len(info), len(comp)
            # align the compressed stream to 16 within the object (43 hdr + info + pad + 8 (_u,_c))
            padding = (16 - (43 + info_sz + 8) % 16) % 16
            buf = info_sz + padding + 8 + comp_len
            hdr = struct.pack("<QQqiiiihB", self.otype, self.oid, self.unk16,
                              buf, info_sz, len(body), comp_len + 8, padding, self.algo)
            payload = info + b"\x00" * padding + struct.pack("<ii", len(body), comp_len) + comp
        else:
            info_sz = len(info); buf = info_sz + len(body)
            hdr = struct.pack("<QQqiiiihB", self.otype, self.oid, self.unk16,
                              buf, info_sz, len(body), 8, 0, self.algo)
            payload = info + body
        return hdr + payload


def _read_obj(data: bytes, pos: int):
    o = struct.unpack_from("<QQqiiiihB", data, pos)
    otype, oid, unk16, buf, info_sz, orig, compf, padding, isc = o
    hdr_end = pos + 43
    if isc == 0:
        info = b""; body = data[hdr_end:hdr_end + buf]
    else:
        info = data[hdr_end:hdr_end + info_sz]
        p = hdr_end + info_sz + padding
        _u, _c = struct.unpack_from("<ii", data, p); p += 8
        comp_len = buf - info_sz - 8 - padding
        body = zlib.decompress(data[p:p + comp_len])
    total = 43 + buf
    raw = data[pos:pos + total]
    return Obj(otype, oid, info, body, isc != 0, raw, unk16=unk16, algo=isc), total


class DpcRepack:
    def __init__(self, path):
        self.path = path
        self.data = open(path, "rb").read()
        self._parse()

    def _parse(self):
        d = self.data
        self.header = bytearray(d[:4096])
        # header offsets (int32 @ these positions, value<<4)
        self.hp_blockdesc = 261
        self.hp_fbsize = 265
        self.hp_fboff = 269
        self.block_desc_off = struct.unpack_from("<i", d, 261)[0] << 4
        self.fb_size = struct.unpack_from("<i", d, 265)[0] << 4
        self.fb_off = struct.unpack_from("<i", d, 269)[0] << 4
        self.map_size = struct.unpack_from("<i", d, 273)[0] << 4
        self.map_off = struct.unpack_from("<i", d, 277)[0] << 4

        # block table
        r = 261  # (unused)
        bt = self.block_desc_off
        self.block_count = struct.unpack_from("<i", d, bt)[0]
        assert self.block_count == 1, f"only single-block supported (got {self.block_count})"
        p = bt + 4
        self.block_unk = d[p:p + 24]; p += 24
        self.files_map_off = struct.unpack_from("<i", d, p)[0] << 4; p += 4
        self.data_files_rel = struct.unpack_from("<i", d, p)[0] << 4; p += 4
        self.data_files_off = self.files_map_off + self.data_files_rel

        # FilesMap header (at files_map_off)
        fm = self.files_map_off
        self.blocks_count = struct.unpack_from("<i", d, fm)[0]
        self.block_offset = struct.unpack_from("<i", d, fm + 4)[0] << 4  # data-block start
        self.fm_crc = d[fm + 8:fm + 40]
        # data-block descriptors
        p = fm + 40
        self.db_descs = []          # [(filesCount, bspad, bsize, crc)]
        for _ in range(self.blocks_count):
            fc = struct.unpack_from("<i", d, p)[0]; p += 4
            bspad = struct.unpack_from("<q", d, p)[0]; p += 8
            bsize = struct.unpack_from("<q", d, p)[0]; p += 8
            crc = struct.unpack_from("<q", d, p)[0]; p += 8
            self.db_descs.append([fc, bspad, bsize, crc])
        # FileMap proper at fm+1496
        self.fm_region = bytearray(d[fm + 1496: self.block_offset])  # copy; patch offsets in-place
        # parse FileBlock entries within fm_region to know positions + offsets
        self.fb_entries = []        # [(rel_pos_of_offset_field, id, type, offset, csize, usize)]
        rp = 0
        n1 = struct.unpack_from("<i", self.fm_region, rp)[0]; rp += 4
        rp = self._read_fm_entries(rp, n1)
        # Requiem tail: skip8, num, 16*num, num2, 4*num2, then count2 + entries2
        rp += 8
        num = struct.unpack_from("<i", self.fm_region, rp)[0]; rp += 4; rp += 16 * num
        num2 = struct.unpack_from("<i", self.fm_region, rp)[0]; rp += 4; rp += 4 * num2
        n2 = struct.unpack_from("<i", self.fm_region, rp)[0]; rp += 4
        rp = self._read_fm_entries(rp, n2)

        # data-block objects (sequential at block_offset)
        self.db_objs = []
        pos = self.block_offset
        total_files = sum(x[0] for x in self.db_descs)
        for _ in range(total_files):
            o, adv = _read_obj(d, pos); self.db_objs.append(o); pos += adv
        self.db_raw_end = pos
        self.gap_datablock = d[pos: self.block_desc_off]   # 0x00 padding verbatim

        # block table raw (table + ff pad up to fb_off)
        self.blocktable_raw = d[self.block_desc_off: self.fb_off]

        # FileBlock objects (textures) — read each at its FileMap offset, in order
        ents = sorted(self.fb_entries, key=lambda e: e[3])
        self.fb_objs = []           # [(id, Obj, orig_offset)]
        for (relpos, fid, ftype, off, cs, us) in ents:
            o, adv = _read_obj(d, off)
            self.fb_objs.append([fid, o, off])
        self.eof = len(d)

    def _read_fm_entries(self, rp, n):
        for _ in range(n):
            fid = struct.unpack_from("<Q", self.fm_region, rp)[0]
            ftype = struct.unpack_from("<Q", self.fm_region, rp + 8)[0]
            off_pos = rp + 16
            off = struct.unpack_from("<i", self.fm_region, off_pos)[0] << 4
            cs = struct.unpack_from("<i", self.fm_region, rp + 20)[0]
            us = struct.unpack_from("<i", self.fm_region, rp + 32)[0]
            self.fb_entries.append((off_pos, fid, ftype, off, cs, us))
            rp += 36
        return rp

    # ---------------------------------------------------------------- #
    def build(self) -> bytes:
        out = bytearray()
        # 1) header (patched at end)
        out += self.header
        assert len(out) == 4096
        # 2) FilesMap: 1496 info region then fm_region (FileMap)
        # We rewrite the 1496 info region from parsed fields (so db_descs can change),
        # keeping crc/unk verbatim.
        info = bytearray()
        info += struct.pack("<i", self.blocks_count)
        info += struct.pack("<i", self.block_offset >> 4)   # data-block start (unchanged: 15664)
        info += self.fm_crc
        for (fc, bspad, bsize, crc) in self.db_descs:
            info += struct.pack("<iqqq", fc, bspad, bsize, crc)
        info += b"\x00" * (1496 - len(info))
        assert len(info) == 1496, len(info)
        out += info
        out += self.fm_region       # FileBlock offsets already patched in-place

        # pad to block_offset (data-block start) — should already be aligned/exact
        assert len(out) == self.block_offset, (len(out), self.block_offset)

        # 3) data-block objects
        db_start = len(out)
        for o in self.db_objs:
            out += o.emit()
        db_bytes = len(out) - db_start
        # 0x00 pad to 16
        pad = align16(len(out)) - len(out)
        out += b"\x00" * pad
        # update data-block descriptor size (single db_desc)
        self.db_descs[0][2] = db_bytes                      # bsize
        self.db_descs[0][1] = db_bytes + pad                # bspad (size incl padding)

        # 4) block table at current pos (16-aligned)
        new_block_desc_off = len(out)
        out += self.blocktable_raw                          # verbatim (internal offsets unchanged)
        # blocktable_raw already includes its trailing ff pad up to old fb_off;
        # ensure 16 alignment of the FileBlock start:
        pad = align16(len(out)) - len(out)
        out += b"\xff" * pad
        new_fb_off = len(out)

        # 5) FileBlock objects, patch their FileMap offset AND csize (textures are
        #    listed in the FileMap; the game reads csize bytes -> a resized object
        #    MUST update csize or the compressed stream is truncated -> crash)
        for i, (fid, o, orig_off) in enumerate(self.fb_objs):
            cur = len(out)
            em = o.emit()
            for (off_pos, e_id, e_type, e_off, cs, us) in self.fb_entries:
                if e_off == orig_off:
                    struct.pack_into("<i", self.fm_region, off_pos, cur >> 4)       # offset<<4
                    struct.pack_into("<i", self.fm_region, off_pos + 4, len(em))    # csize = on-disk obj len
                    break
            out += em
            pad = align16(len(out)) - len(out)
            out += b"\xff" * pad
        new_fb_size = len(out) - new_fb_off

        # fm_region was patched AFTER we copied it into out (step 2). Re-copy patched fm_region.
        struct.pack_into  # noop
        fm_start = 4096 + 1496
        out[fm_start:fm_start + len(self.fm_region)] = self.fm_region

        # re-emit the FilesMap info too (db_descs changed) — rewrite region [4096:4096+1496]
        info = bytearray()
        info += struct.pack("<i", self.blocks_count)
        info += struct.pack("<i", self.block_offset >> 4)
        info += self.fm_crc
        for (fc, bspad, bsize, crc) in self.db_descs:
            info += struct.pack("<iqqq", fc, bspad, bsize, crc)
        info += b"\x00" * (1496 - len(info))
        out[4096:4096 + 1496] = info

        # 6) patch header offsets
        struct.pack_into("<i", out, self.hp_blockdesc, new_block_desc_off >> 4)
        struct.pack_into("<i", out, self.hp_fboff, new_fb_off >> 4)
        struct.pack_into("<i", out, self.hp_fbsize, new_fb_size >> 4)
        return bytes(out)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("dpc", nargs="?", default=r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC")
    ap.add_argument("--out", help="write rebuilt DPC here")
    args = ap.parse_args()
    D = DpcRepack(args.dpc)
    print(f"parsed: blockDescOff={D.block_desc_off} fbOff={D.fb_off} fbSize={D.fb_size} "
          f"dataBlock@{D.block_offset} dbObjs={len(D.db_objs)} fbObjs={len(D.fb_objs)}")
    rebuilt = D.build()
    orig = D.data
    print(f"orig={len(orig)} rebuilt={len(rebuilt)} identical={rebuilt==orig}")
    if rebuilt != orig:
        # first diff
        n = min(len(orig), len(rebuilt))
        for i in range(n):
            if orig[i] != rebuilt[i]:
                print(f"first diff @ {i} (0x{i:X}): orig={orig[i-4:i+8].hex()} new={rebuilt[i-4:i+8].hex()}")
                break
        print(f"len diff: {len(rebuilt)-len(orig)}")
    if args.out:
        open(args.out, "wb").write(rebuilt); print("wrote", args.out)
