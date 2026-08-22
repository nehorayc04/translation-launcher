"""
gl_rpkg.py — pure-Python read-only reader for the Glacier Engine RPKG v2 ("2KPR")
container, as shipped by 007 First Light (IO Interactive).

Format cracked from:
  - Picoseconds/GlacierFormats  hitman3_rpkg2.ksy   (container header + tables)
  - glacier-modding/RPKG-Tool  (first-light branch)  crypto.cpp  (resource XOR)
  - AnthonyFuller/TonyTools  HMLanguages Languages.cpp (LOCR/DLGE/CLNG formats)

RPKG v2 (base, no patch) layout — verified empirically against chunk0.rpkg:
  Header (25 bytes):
    0x00  char[4]  magic          "2KPR"
    0x04  byte[9]  unknown
    0x0d  u32      file_count
    0x11  u32      table_offset    (metadata table starts at table_offset + 25)
    0x15  u32      table_size
  File table 1 (hash table), file_count x 20 bytes, starting at 0x19:
    0x00  u64  hash             (IOI 8-byte resource id)
    0x08  u64  data_offset      (absolute offset of the resource bytes in the file)
    0x10  u32  data_size        (on-disk size; low 30 bits = compressed size, 0 => stored;
                                 bit 31 set => NOT xored, clear => xored  [see note])
  File table 2 (metadata), file_count entries, starting at table_offset + 25:
    0x00  char[4]  resource_type    (stored REVERSED: "RCOL"->LOCR, "EGLD"->DLGE, "GNLC"->CLNG)
    0x04  u32      references_size  (byte size of the references block, 0 => none)
    0x08  u32      states_size      (usually 0)
    0x0c  u32      size_final       (decompressed size)
    0x10  u32      size_in_memory
    0x14  u32      size_in_video_memory
    [references_size bytes]  [states_size bytes]

Resource read: seek data_offset, read on-disk bytes; if xored -> xor_data();
if compressed (low30 != 0) -> LZ4 raw block decompress to size_final; else raw.

Read-only. Never writes a game file.
"""
import struct, sys, os
import lz4.block

MAGIC = b"2KPR"
XOR_ARRAY = bytes([0xDC, 0x45, 0xA6, 0x9C, 0xD3, 0x72, 0x4C, 0xAB])


def xor_data(buf: bytearray) -> bytearray:
    for i in range(len(buf)):
        buf[i] ^= XOR_ARRAY[i & 7]
    return buf


class Resource:
    __slots__ = ("hash", "offset", "on_disk_size", "xored", "comp_size",
                 "rtype", "size_final", "raw_meta")

    def __init__(self, hsh, offset, on_disk_size, rtype, size_final, raw_meta=b""):
        self.hash = hsh
        self.offset = offset
        self.on_disk_size = on_disk_size
        # data_size: bit 0x80000000 SET => xored (per RPKG-Tool import_rpkg.cpp);
        # low 30 bits = compressed size (0 => stored / not lz4'd)
        self.xored = (on_disk_size & 0x80000000) == 0x80000000
        self.comp_size = on_disk_size & 0x3FFFFFFF
        self.rtype = rtype
        self.size_final = size_final
        # the verbatim file-table-2 (metadata) entry bytes for this resource:
        # char[4] type(reversed) + u32 ref_table_size + u32 size_final + u32 mem
        # + u32 vmem + [ref block]. Copied unchanged into a patch (only size_final
        # is patched when the override's decompressed length differs).
        self.raw_meta = raw_meta

    @property
    def lz4ed(self):
        return self.comp_size != 0

    @property
    def read_size(self):
        return self.comp_size if self.lz4ed else self.size_final

    def hex(self):
        return f"{self.hash:016X}"

    def name(self):
        return f"{self.hex()}.{self.rtype}"


class RPKG:
    def __init__(self, path, is_patch=False):
        self.path = path
        self.is_patch = is_patch     # patch chunk (header 29 + patch_count deletion list)
        self.resources = []          # list[Resource], index-aligned to both tables
        self._by_type = {}           # rtype -> list[int index]
        self._by_hash = {}           # hash -> index
        self._parse()

    def _parse(self):
        with open(self.path, "rb") as f:
            hdr = f.read(29)
            if hdr[:4] != MAGIC:
                raise ValueError(f"not a 2KPR RPKG: magic={hdr[:4]!r}")
            self.v2_header = hdr[4:13]  # the 9 "unknown" header bytes (copied on write)
            file_count = struct.unpack_from("<I", hdr, 13)[0]
            table_offset = struct.unpack_from("<I", hdr, 17)[0]
            table_size = struct.unpack_from("<I", hdr, 21)[0]
            self.file_count = file_count
            self.table_offset = table_offset
            self.table_size = table_size
            if self.is_patch:
                patch_count = struct.unpack_from("<I", hdr, 25)[0]
                self.patch_count = patch_count
                body_start = 29 + patch_count * 8   # skip patch header + deletion list
            else:
                self.patch_count = 0
                body_start = 25                     # base header

            # File table 1
            f.seek(body_start)
            t1 = f.read(file_count * 20)
            # File table 2
            f.seek(body_start + table_offset)
            t2 = f.read(table_size)

        # parse t2 sequentially (variable length), validate exact consumption
        types = []
        sizes_final = []
        # HashResource entry (007 First Light / first-light branch — the
        # reference_table_dummy u32 present in Hitman was REMOVED, so the base
        # entry is 20 bytes, not 24):
        #   +0  char[4]  resource_type (reversed)
        #   +4  u32      reference_table_size (0 => no references block)
        #   +8  u32      size_final (decompressed size)
        #   +12 u32      size_in_memory
        #   +16 u32      size_in_video_memory
        # References block (only if reference_table_size > 0):
        #   +0  u32  depends_count (low 30 bits = count; high bits = flags)
        #   then count x { u8 flag } and count x { u64 hash }  => 4 + 9*count bytes
        p = 0
        metas = []          # verbatim file-table-2 entry bytes per resource
        for i in range(file_count):
            start = p
            rtype = t2[p:p + 4][::-1].decode("latin1")
            ref_table_size = struct.unpack_from("<I", t2, p + 4)[0]
            size_final = struct.unpack_from("<I", t2, p + 8)[0]
            types.append(rtype)
            sizes_final.append(size_final)
            p += 20
            if ref_table_size > 0:
                depends_count = struct.unpack_from("<I", t2, p)[0] & 0x3FFFFFFF
                p += 4 + depends_count * 9
            metas.append(t2[start:p])
        self._t2_consumed = p
        self._t2_valid = (p == table_size)

        # build resources
        for i in range(file_count):
            hsh, off, dsz = struct.unpack_from("<QQI", t1, i * 20)
            r = Resource(hsh, off, dsz, types[i], sizes_final[i], metas[i])
            self.resources.append(r)
            self._by_type.setdefault(r.rtype, []).append(i)
            self._by_hash[hsh] = i

    def by_hash(self, hsh):
        return self.resources[self._by_hash[hsh]] if hsh in self._by_hash else None

    def read_hash(self, hsh):
        return self.read(self._by_hash[hsh])

    def type_counts(self):
        return {t: len(v) for t, v in sorted(self._by_type.items(),
                                             key=lambda kv: -len(kv[1]))}

    def indices(self, rtype):
        return self._by_type.get(rtype, [])

    def read(self, i, decrypt_xor=True) -> bytes:
        r = self.resources[i]
        with open(self.path, "rb") as f:
            f.seek(r.offset)
            data = bytearray(f.read(r.read_size))
        if r.xored and decrypt_xor:
            xor_data(data)
        if r.lz4ed:
            return lz4.block.decompress(bytes(data), uncompressed_size=r.size_final)
        return bytes(data)


def _cli():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("rpkg")
    ap.add_argument("cmd", choices=["info", "types", "find", "dump"])
    ap.add_argument("arg", nargs="?", default="")
    a = ap.parse_args()
    r = RPKG(a.rpkg)
    if a.cmd == "info":
        print(f"file: {a.rpkg}")
        print(f"file_count={r.file_count} table_offset={r.table_offset} "
              f"table_size={r.table_size}")
        print(f"metadata parse valid (consumed==table_size): {r._t2_valid} "
              f"(consumed {r._t2_consumed} / {r.table_size})")
    elif a.cmd == "types":
        for t, n in r.type_counts().items():
            print(f"  {t:6s} {n}")
    elif a.cmd == "find":
        idxs = r.indices(a.arg)
        print(f"{a.arg}: {len(idxs)} resources")
        for i in idxs[:10]:
            res = r.resources[i]
            print(f"  [{i}] {res.name()} off={res.offset} "
                  f"disk={res.read_size} final={res.size_final} "
                  f"lz4={res.lz4ed} xor={res.xored}")
    elif a.cmd == "dump":
        i = int(a.arg)
        data = r.read(i)
        res = r.resources[i]
        out = f"C:/tmp/{res.hex()}.{res.rtype}.bin"
        open(out, "wb").write(data)
        print(f"wrote {out} ({len(data)} bytes)")


if __name__ == "__main__":
    _cli()
