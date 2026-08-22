#!/usr/bin/env python3
"""rpf_lazy.py - LAZY read-only RPF7 walker for GTA V (Legacy *and* Enhanced).

`tools/rpf7.py` (the write path) materialises every file's bytes while parsing, which
costs ~3 GB of RAM on `update.rpf`. Extraction only ever needs one or two files, so this
module walks the TOC and reads a payload **on demand**.

Field decoding is byte-identical to `rpf7.py` - in particular the two traps that
silently corrupt an RPF if missed:

  * the data offset is **23 bits**, and **bit 63 is the RESOURCE flag** (.ymt/.ydr/...).
    Reading it as a 24-bit offset puts every resource file 0x800000 blocks too high.
  * **`FileSize == 0` means the entry is STORED RAW** and its real length lives in
    `FileUncompressedSize` - that is why a large nested archive first reads as size 0.

Compression is RAW DEFLATE (zlib wbits=-15), the RAGE/OpenIV convention.

Only OPEN archives can be walked. Every shipped GTA V archive (Legacy *and* Enhanced)
is NG-encrypted; the OPEN copies are the ones OpenIV writes into the `mods\\` folder.
"""
import mmap
import struct
import zlib

MAGIC = 0x52504637          # '7FPR'
DIR_MARK = 0x7FFFFF00
ENC_OPEN = 0x4E45504F
ENC_NAMES = {0: "NONE", ENC_OPEN: "OPEN", 0x0FFFFFF9: "AES", 0x0FEFFFFF: "NG"}

# A binary file entry's last u32 is **IsEncrypted**, not a generic flag word. An archive
# with an OPEN table-of-contents can still hold per-file AES-encrypted payloads - every
# vanilla-copied archive (e.g. x64b.rpf) does, while the archives OpenIV rewrites do not.
# Decryption is the public GTA5 AES-256-ECB key applied 16 times.
GTA5_AES_KEY = bytes.fromhex(
    "b38973af8b9e263a8df170321442b3938bd3f21fa4d04dff882e04660ff99dfd")


def aes_decrypt(data):
    """16 rounds of AES-256-ECB over the whole 16-byte-aligned prefix."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    n = len(data) - (len(data) % 16)
    body, tail = bytes(data[:n]), bytes(data[n:])
    for _ in range(16):
        dec = Cipher(algorithms.AES(GTA5_AES_KEY), modes.ECB(),
                     backend=default_backend()).decryptor()
        body = dec.update(body) + dec.finalize()
    return body + tail


class Entry:
    __slots__ = ("path", "name", "is_dir", "off", "csize", "usize", "flags", "res")

    def __init__(self, path, name, is_dir, off=0, csize=0, usize=0, flags=0, res=0):
        self.path, self.name, self.is_dir = path, name, is_dir
        self.off, self.csize, self.usize, self.flags, self.res = off, csize, usize, flags, res

    @property
    def on_disk(self):
        """Bytes occupied on disk: csize when compressed, usize when stored raw."""
        return self.csize if self.csize != 0 else self.usize

    def __repr__(self):
        return f"<Entry {self.path} {'dir' if self.is_dir else self.on_disk}>"


def encryption_of(buf, base=0):
    magic, ec, nl, enc = struct.unpack_from("<IIII", buf, base)
    if magic != MAGIC:
        return None, 0, 0
    return ENC_NAMES.get(enc, hex(enc)), ec, nl


class LazyRpf:
    """Read-only view of an OPEN RPF7 whose header sits at `base` inside `buf`."""

    def __init__(self, buf, base=0, prefix=""):
        self.buf, self.base, self.prefix = buf, base, prefix
        magic, ec, nl, enc = struct.unpack_from("<IIII", buf, base)
        if magic != MAGIC:
            raise ValueError(f"not an RPF7 at {base}")
        if enc != ENC_OPEN:
            raise ValueError(
                f"archive is {ENC_NAMES.get(enc, hex(enc))}-encrypted, not OPEN - "
                "only the OpenIV-decrypted mods\\ copies can be read")
        self.entry_count, self.names_len = ec, nl
        ent_off = base + 16
        self._names = bytes(buf[ent_off + ec * 16: ent_off + ec * 16 + nl])
        self._raw = [bytes(buf[ent_off + i * 16: ent_off + i * 16 + 16]) for i in range(ec)]
        self._entries = None

    def _cstr(self, off):
        e = self._names.find(b"\x00", off)
        return self._names[off:(e if e >= 0 else len(self._names))].decode("latin-1", "replace")

    def entries(self):
        """Flat list of Entry, paths relative to this archive (forward slashes)."""
        if self._entries is not None:
            return self._entries
        out = []

        def walk(idx, prefix, depth):
            if idx < 0 or idx >= len(self._raw) or depth > 64:
                return
            b = self._raw[idx]
            if struct.unpack_from("<I", b, 4)[0] == DIR_MARK:
                name = self._cstr(struct.unpack_from("<I", b, 0)[0])
                ei = struct.unpack_from("<I", b, 8)[0]
                cnt = struct.unpack_from("<I", b, 12)[0]
                here = prefix if idx == 0 else f"{prefix}{name}/"
                if idx != 0:
                    out.append(Entry(here.rstrip("/"), name, True))
                for c in range(ei, ei + cnt):
                    walk(c, here, depth + 1)
                return
            packed = struct.unpack_from("<Q", b, 0)[0]
            name = self._cstr(packed & 0xFFFF)
            out.append(Entry(
                prefix + name, name, False,
                off=self.base + ((packed >> 40) & 0x7FFFFF) * 512,
                csize=(packed >> 16) & 0xFFFFFF,
                usize=struct.unpack_from("<I", b, 8)[0],
                flags=struct.unpack_from("<I", b, 12)[0],
                res=(packed >> 63) & 1,
            ))

        walk(0, "", 0)
        self._entries = out
        return out

    def get(self, path):
        want = path.replace("\\", "/").lower()
        for e in self.entries():
            if e.path.lower() == want:
                return e
        return None

    def read(self, path_or_entry):
        """Return the plaintext, decompressed bytes of one file.

        Order matters: a payload is AES-encrypted **around** the deflate stream, so it
        must be decrypted first and inflated second.
        """
        e = path_or_entry if isinstance(path_or_entry, Entry) else self.get(path_or_entry)
        if e is None:
            raise KeyError(path_or_entry)
        raw = bytes(self.buf[e.off: e.off + e.on_disk])
        if e.res == 0 and (e.flags & 1):       # binary entry marked encrypted
            raw = aes_decrypt(raw)
        if e.csize == 0:                       # stored raw
            return raw
        return zlib.decompress(raw[:e.csize], -15)   # RAW deflate, no zlib header

    def nested(self, path):
        """Open a nested .rpf that is stored RAW inside this one."""
        e = self.get(path)
        if e is None:
            raise KeyError(path)
        if e.csize != 0:
            raise ValueError(f"{path} is compressed; nested RPFs are expected stored raw")
        return LazyRpf(self.buf, e.off, prefix=self.prefix + e.path + "/")


def open_file(path):
    """mmap a .rpf from disk -> (LazyRpf, mmap, file). Caller closes mm and f."""
    f = open(path, "rb")
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    return LazyRpf(mm), mm, f


if __name__ == "__main__":
    import sys
    rpf, mm, f = open_file(sys.argv[1])
    ents = rpf.entries()
    files = [e for e in ents if not e.is_dir]
    print(f"{sys.argv[1]}\n  entries={rpf.entry_count} files={len(files)} names={rpf.names_len}")
    for e in files[:int(sys.argv[2]) if len(sys.argv) > 2 else 20]:
        print(f"   {e.on_disk:>10,}  {e.path}")
    mm.close()
    f.close()
