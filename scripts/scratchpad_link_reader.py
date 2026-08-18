import struct, zlib, sys, os

MAGIC = 0x00077DF9
ZLIB_SECOND = {0x01, 0x5e, 0x9c, 0xda}

class LinkData:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.data = f.read()
        code, files, mult, pad = struct.unpack_from("<IIII", self.data, 0)
        assert code == MAGIC, f"bad magic 0x{code:08x} in {path}"
        self.files = files
        self.mult = mult
        self.entries = []
        off = 16
        for i in range(files):
            eo, epad, csize, dsize = struct.unpack_from("<IIII", self.data, off)
            self.entries.append((eo, epad, csize, dsize))
            off += 16

    def raw(self, i):
        eo, epad, csize, dsize = self.entries[i]
        start = eo * self.mult
        return self.data[start:start+csize]

    def read(self, i):
        """Return decompressed bytes for entry i (mirrors AoT2 toolkit decompress_files heuristic)."""
        eo, epad, csize, dsize = self.entries[i]
        raw = self.raw(i)
        if dsize == 0:
            return raw
        # scan for zlib streams and concatenate decompressed output
        chunk_offsets = []
        offset = 0
        data = raw
        while offset < len(data) - 1:
            pos = data.find(b'\x78', offset)
            if pos == -1 or pos >= len(data) - 1:
                break
            if data[pos+1] in ZLIB_SECOND and (0x78*256 + data[pos+1]) % 31 == 0:
                try:
                    dobj = zlib.decompressobj()
                    dobj.decompress(data[pos:pos+256])
                    chunk_offsets.append(pos)
                    offset = pos + 2
                except zlib.error:
                    offset = pos + 1
            else:
                offset = pos + 1
        if not chunk_offsets:
            return raw
        chunks = []
        for i2, start in enumerate(chunk_offsets):
            end = chunk_offsets[i2+1] if i2+1 < len(chunk_offsets) else len(data)
            dobj = zlib.decompressobj()
            try:
                chunks.append(dobj.decompress(data[start:end]))
            except zlib.error:
                pass
        return b"".join(chunks)


def is_datatable(buf):
    if len(buf) < 8:
        return False
    count = struct.unpack_from("<I", buf, 0)[0]
    if count == 0 or count > 2_000_000:
        return False
    if 4 + count*8 > len(buf):
        return False
    first_off = struct.unpack_from("<I", buf, 4)[0]
    est = 4 + count*8
    est_aligned = (est + 15) & ~15
    return first_off == est or first_off == est_aligned

def parse_datatable(buf):
    count = struct.unpack_from("<I", buf, 0)[0]
    out = []
    for i in range(count):
        off, size = struct.unpack_from("<II", buf, 4 + i*8)
        if off > len(buf):
            out.append(None)
            continue
        maxsize = min(size, len(buf)-off)
        out.append(buf[off:off+maxsize])
    return out

def read_cstring(b):
    idx = b.find(b"\x00")
    raw = b if idx == -1 else b[:idx]
    for enc in ("utf-8", "cp932", "latin1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return repr(raw)

if __name__ == "__main__":
    path = sys.argv[1]
    ld = LinkData(path)
    print(f"{path}: files={ld.files} mult={ld.mult}")
