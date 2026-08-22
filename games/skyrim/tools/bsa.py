"""Pure-Python Bethesda BSA reader (v103/104 = Skyrim LE, v105 = Skyrim SE / AE).

Read-only. Format per UESP + the community bsarch implementation.

Header (36 B):
    char[4] "BSA\0" | u32 version | u32 folderRecordOffset(=36)
    u32 archiveFlags | u32 folderCount | u32 fileCount
    u32 totalFolderNameLength | u32 totalFileNameLength | u32 fileFlags

archiveFlags: 0x1 dir-names 0x2 file-names 0x4 compressed-by-default
              0x100 embed-file-names

Folder record: v105 -> <QIIQ> (hash, count, pad, offset)   [24 B]
               v10x -> <QII>  (hash, count, offset)        [16 B]
NOTE the folder record's `offset` is (real file-record offset + totalFileNameLength).

File record: <QII> (hash, size, offset).  size bit30 (0x40000000) TOGGLES compression
relative to the archive default; the real size is size & 0x3FFFFFFF.

File data: [u8 len + path  if embed-file-names] [u32 originalSize if compressed] payload.
Compression: v104 -> zlib, v105 -> LZ4 frame.

CLI:  python bsa.py list <archive.bsa> [substr]
      python bsa.py extract <archive.bsa> <outdir> [substr]
      python bsa.py get <archive.bsa> <internal/path> <outfile>
"""
from __future__ import annotations

import os
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path

MAGIC = b"BSA\x00"

AF_DIR_NAMES = 0x1
AF_FILE_NAMES = 0x2
AF_COMPRESSED = 0x4
AF_EMBED_NAMES = 0x100

_COMP_TOGGLE = 0x40000000
_SIZE_MASK = 0x3FFFFFFF


@dataclass
class BsaFile:
    path: str          # "interface/fonts_en.swf" (lower-case, forward slashes)
    size_raw: int      # as stored (with the toggle bit)
    offset: int

    @property
    def size(self) -> int:
        return self.size_raw & _SIZE_MASK

    def compressed(self, archive_flags: int) -> bool:
        default = bool(archive_flags & AF_COMPRESSED)
        return default != bool(self.size_raw & _COMP_TOGGLE)


class Bsa:
    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self.files: list[BsaFile] = []
        self._by_path: dict[str, BsaFile] = {}
        self._parse()

    # ---------------------------------------------------------------- parse
    def _parse(self) -> None:
        with self.path.open("rb") as f:
            head = f.read(36)
            if head[:4] != MAGIC:
                raise ValueError(f"not a BSA: {head[:4]!r}")
            (self.version, folder_off, self.archive_flags, folder_count,
             file_count, total_folder_name_len, total_file_name_len,
             self.file_flags) = struct.unpack("<8I", head[4:36])
            if self.version not in (103, 104, 105):
                raise ValueError(f"unsupported BSA version {self.version}")

            f.seek(folder_off)
            rec_fmt = "<QIIQ" if self.version >= 105 else "<QII"
            rec_len = struct.calcsize(rec_fmt)
            folders = []
            raw = f.read(rec_len * folder_count)
            for i in range(folder_count):
                vals = struct.unpack_from(rec_fmt, raw, i * rec_len)
                count = vals[1]
                off = vals[3] if self.version >= 105 else vals[2]
                folders.append((count, off - total_file_name_len))

            # file-record blocks
            entries: list[tuple[str, int, int]] = []   # (folder, size_raw, offset)
            for count, off in folders:
                f.seek(off)
                folder_name = ""
                if self.archive_flags & AF_DIR_NAMES:
                    ln = f.read(1)[0]
                    folder_name = f.read(ln).rstrip(b"\x00").decode("cp1252")
                blk = f.read(count * 16)
                for i in range(count):
                    _h, size_raw, o = struct.unpack_from("<QII", blk, i * 16)
                    entries.append((folder_name, size_raw, o))

            # file-name block (one NUL-terminated name per file, in the same order)
            names: list[str] = []
            if self.archive_flags & AF_FILE_NAMES:
                blob = f.read(total_file_name_len)
                names = [n.decode("cp1252") for n in blob.split(b"\x00")[:file_count]]

            for i, (folder, size_raw, off) in enumerate(entries):
                name = names[i] if i < len(names) else f"__unnamed_{i:06d}"
                p = (folder.replace("\\", "/") + "/" + name).lstrip("/").lower()
                bf = BsaFile(p, size_raw, off)
                self.files.append(bf)
                self._by_path[p] = bf

    # ----------------------------------------------------------------- read
    def read(self, item: str | BsaFile) -> bytes:
        bf = self._by_path[item.replace("\\", "/").lower()] if isinstance(item, str) else item
        with self.path.open("rb") as f:
            f.seek(bf.offset)
            n = bf.size
            if self.archive_flags & AF_EMBED_NAMES:
                ln = f.read(1)[0]
                f.read(ln)
                n -= ln + 1
            if not bf.compressed(self.archive_flags):
                return f.read(n)
            orig = struct.unpack("<I", f.read(4))[0]
            payload = f.read(n - 4)
            if self.version >= 105:
                import lz4.frame
                out = lz4.frame.decompress(payload)
            else:
                out = zlib.decompress(payload)
            if len(out) != orig:
                raise ValueError(f"{bf.path}: decompressed {len(out)} != {orig}")
            return out

    def __contains__(self, p: str) -> bool:
        return p.replace("\\", "/").lower() in self._by_path

    def find(self, substr: str) -> list[BsaFile]:
        s = substr.lower()
        return [b for b in self.files if s in b.path]


# ------------------------------------------------------------------- CLI
def _main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    cmd, arc = argv[1], argv[2]
    b = Bsa(arc)
    if cmd == "list":
        sub = argv[3].lower() if len(argv) > 3 else ""
        hits = [x for x in b.files if sub in x.path]
        print(f"# v{b.version} flags=0x{b.archive_flags:x} files={len(b.files)} "
              f"match={len(hits)}")
        for x in hits:
            print(f"{x.size:>10}  {'C' if x.compressed(b.archive_flags) else ' '}  {x.path}")
        return 0
    if cmd == "extract":
        out = Path(argv[3])
        sub = argv[4].lower() if len(argv) > 4 else ""
        n = 0
        for x in b.files:
            if sub and sub not in x.path:
                continue
            dst = out / x.path
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(b.read(x))
            n += 1
        print(f"extracted {n} -> {out}")
        return 0
    if cmd == "get":
        Path(argv[4]).write_bytes(b.read(argv[3]))
        print(f"ok -> {argv[4]}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
