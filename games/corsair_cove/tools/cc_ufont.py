#!/usr/bin/env python3
"""
cc_ufont.py - codec for Corsair Cove's cooked font files (`*.ufont`).

Corsair Cove (Unreal Engine 5, WinGDK) cooks every UFontFace with its TTF payload
as a SEPARATE loose bulk file inside the legacy pak (`pakchunk0_s25-WinGDK.pak`),
NOT inside the IoStore container. That makes the whole font workstream a plain
loose-file override -- no IoStore repack needed.

LAYOUT (verified byte-exact on all 18 shipped .ufont):

    [u32 LE  sfntSize] [sfnt payload: sfntSize bytes] [4 bytes 0x00000000]

  * `sfntSize` equals the sfnt's own table-directory end (max(offset+length),
    4-aligned) on 18/18 files -- so the prefix is the real payload length.
  * The trailing 4 zero bytes are always present and always zero.

NOTE this differs from Until Dawn, whose `.ufont` is a BARE TTF at offset 0.
Always dump the first bytes before assuming a sibling game's layout.

CLI:
    cc_ufont.py info    <file.ufont>
    cc_ufont.py extract <file.ufont> <out.ttf>
    cc_ufont.py wrap    <in.ttf> <out.ufont>
    cc_ufont.py selftest <dir-with-ufonts>
"""
import glob
import os
import struct
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TAIL = b"\x00\x00\x00\x00"


def read(path):
    """Return the bare sfnt (TTF/OTF) bytes inside a .ufont."""
    with open(path, "rb") as f:
        blob = f.read()
    return unwrap(blob)


def unwrap(blob):
    if len(blob) < 8:
        raise ValueError("too short to be a .ufont")
    n = struct.unpack_from("<I", blob, 0)[0]
    if 4 + n + len(TAIL) != len(blob):
        raise ValueError(
            "unexpected .ufont layout: prefix=%d file=%d (expected %d)"
            % (n, len(blob), 4 + n + len(TAIL))
        )
    return blob[4:4 + n]


def wrap(sfnt):
    """Wrap bare sfnt bytes back into the .ufont container."""
    return struct.pack("<I", len(sfnt)) + sfnt + TAIL


def write(path, sfnt):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(wrap(sfnt))
    return len(sfnt)


def sfnt_end(sfnt):
    """Length implied by the sfnt table directory (4-aligned) -- the cross-check
    that proves the u32 prefix really is the payload size."""
    num_tables = struct.unpack_from(">H", sfnt, 4)[0]
    end = 0
    for i in range(num_tables):
        o = 12 + i * 16
        off, ln = struct.unpack_from(">II", sfnt, o + 8)
        end = max(end, off + ln)
    return (end + 3) & ~3


def selftest(root):
    files = sorted(glob.glob(os.path.join(root, "**", "*.ufont"), recursive=True))
    if not files:
        print("no .ufont under", root)
        return 1
    bad = 0
    for p in files:
        raw = open(p, "rb").read()
        try:
            sfnt = unwrap(raw)
        except Exception as e:
            print("FAIL unwrap", os.path.basename(p), e)
            bad += 1
            continue
        ok_dir = sfnt_end(sfnt) == len(sfnt)
        ok_rt = wrap(sfnt) == raw
        if not (ok_dir and ok_rt):
            bad += 1
        print("%-42s %9dB  dir_ok=%s  byte-identical=%s"
              % (os.path.basename(p), len(raw), ok_dir, ok_rt))
    print("\n%d/%d byte-identical round-trip" % (len(files) - bad, len(files)))
    return 1 if bad else 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "info"
    if cmd == "selftest":
        return selftest(argv[2])
    if cmd == "info":
        sfnt = read(argv[2])
        print("sfnt bytes:", len(sfnt), "table-dir end:", sfnt_end(sfnt))
        return 0
    if cmd == "extract":
        open(argv[3], "wb").write(read(argv[2]))
        print("wrote", argv[3])
        return 0
    if cmd == "wrap":
        write(argv[3], open(argv[2], "rb").read())
        print("wrote", argv[3])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
