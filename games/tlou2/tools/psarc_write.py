#!/usr/bin/env python3
r"""
psarc_write.py — build a small PLAIN PSARC v1.4 (zlib) override for TLOU Part II
Remastered, to be dropped into the game's `mods\` folder and mounted by
ndmodloader at higher priority than core.psarc.

WHY plain PSARC (no DSAR wrapper): confirmed from the reference tools (UnPSARC /
ndarc) — ndmodloader loads ANY `.psarc` in `mods\`; it does NOT have to be the
DSAR/LZ4 DirectStorage container the game ships. ndarc itself can emit plain
`zlib` PSARCs and they load. So an override only needs a valid inner PSARC v1.4
whose TOC md5-hashes resolve the overridden paths. Contrast games/tlou1, whose
loose-file override did NOT work and required a full core.psarc repack.

Inner PSARC v1.4 (big-endian), matching the shipping core.psarc exactly:
  header 32B: "PSAR" | u16 verMaj(1),verMin(4) | "zlib" | u32 tocSize | u32 entrySize(30)
              | u32 numFiles | u32 blockSize(0x10000) | u32 flags(0xc)
  numFiles x 30B TOC entry: 16 md5(ASCII path) | u32 blockStart(BE) | u40 origSize(BE) | u40 offset(BE)
  block-size table: one u16-BE per data block (blockSize 0x10000 -> 2 bytes). 0 == full raw block.
  entry 0 = manifest: md5 = 16 zero bytes; content = the file paths, NUL-separated
            (the shipping core.psarc uses \x00, verified on this install).
  Entries 1..n are SORTED by md5(path) ascending (the game binary-searches the TOC).
  md5 is over Encoding.ASCII of the exact path string.

CLI:
  python psarc_write.py build <out.psarc> <archive/path=localfile> [...]
  python psarc_write.py verify <a.psarc>          # read back a plain PSARC (self-check)
"""
import os, sys, struct, zlib, hashlib, argparse

BLOCK_SIZE = 0x10000
ARCHIVE_FLAGS = 0xC          # matches shipping core.psarc
MANIFEST_SEP = b"\x00"       # shipping core.psarc uses NUL


def _u40(v):
    return v.to_bytes(5, "big")


def _md5(path):
    return hashlib.md5(path.encode("ascii")).digest()


def _blocks(data, comp):
    """-> (table_values, blob). zlib-compress each blockSize chunk; store raw if it
    doesn't help (0 == a full raw block of blockSize)."""
    table, blob = [], bytearray()
    for i in range(0, len(data), BLOCK_SIZE):
        raw = data[i:i + BLOCK_SIZE]
        rawlen = len(raw)
        z = zlib.compress(raw, 9) if comp else b""
        if comp and len(z) < rawlen:
            table.append(len(z)); blob += z
        else:
            table.append(0 if rawlen == BLOCK_SIZE else rawlen); blob += raw
    return table, bytes(blob)


def build(files, block_size=BLOCK_SIZE, flags=ARCHIVE_FLAGS, compress=True):
    """files: {archive_path: bytes}. Returns a plain PSARC v1.4 bytes.

    compress=True  -> zlib each block (smaller mod).
    compress=False -> STORED blocks, exactly how the shipping core.psarc holds
                      its files (core is a DSAR: the inner PSARC is stored, the
                      DSAR/LZ4 outer does the compression). The TLOU2R engine reads
                      the inner-PSARC blocks per the block-table; a zlib inner block
                      is decoded WRONG by the engine (it shows "UNKNOWN STRING"),
                      so a mod that overrides in place must store its blocks raw."""
    paths = sorted(files.keys(), key=_md5)          # entries 1..n md5-ascending
    manifest = MANIFEST_SEP.join(p.encode("ascii") for p in paths)

    # entry list: [ (name_hash, data) ], entry 0 = manifest (zero hash)
    ents = [(b"\x00" * 16, manifest)] + [(_md5(p), files[p]) for p in paths]
    n = len(ents)

    # compress each, collect global block table + per-entry (blockStart, origSize, blob)
    block_table, plan = [], []
    for name_hash, data in ents:
        bstart = len(block_table)
        table, blob = _blocks(data, comp=compress)
        block_table += table
        plan.append([name_hash, bstart, len(data), blob])

    nb = 2                                           # blockSize 0x10000 -> u16 table
    toc_size = 32 + n * 30 + len(block_table) * nb

    # assign absolute data offsets (write order == entry order)
    off = toc_size
    for pl in plan:
        pl.append(off)                               # pl[4] = fileOffset
        off += len(pl[3])

    out = bytearray()
    out += b"PSAR" + struct.pack(">HH", 1, 4) + b"zlib"
    out += struct.pack(">IIIII", toc_size, 30, n, block_size, flags)
    for name_hash, bstart, orig, blob, foff in plan:
        out += name_hash + struct.pack(">I", bstart) + _u40(orig) + _u40(foff)
    for v in block_table:
        out += v.to_bytes(nb, "big")
    assert len(out) == toc_size, (len(out), toc_size)
    for pl in plan:
        out += pl[3]
    return bytes(out)


# ---- verify reader (plain PSARC, zlib) — for the self-test only ----------------
def verify_read(data):
    assert data[:4] == b"PSAR", data[:4]
    tocSize, entSize, nFiles, blk, flags = struct.unpack_from(">IIIII", data, 12)
    ents = []
    for i in range(nFiles):
        e = data[32 + i * 30:32 + (i + 1) * 30]
        ents.append((e[0:16], struct.unpack(">I", e[16:20])[0],
                     int.from_bytes(e[20:25], "big"), int.from_bytes(e[25:30], "big")))
    table_off = 32 + nFiles * 30
    tb = data[table_off:tocSize]
    bt = [int.from_bytes(tb[j:j + 2], "big") for j in range(0, len(tb), 2)]

    def read(bstart, orig, foff):
        outb = bytearray(); rem = orig; bi = bstart; pos = foff
        while rem > 0:
            cs = bt[bi]; bi += 1
            rawlen = min(blk, rem)
            if cs == 0:
                outb += data[pos:pos + blk][:rawlen]; pos += blk
            else:
                chunk = data[pos:pos + cs]; pos += cs
                outb += chunk[:rawlen] if cs >= rawlen else zlib.decompress(chunk)
            rem -= rawlen
        return bytes(outb)

    man = read(ents[0][1], ents[0][2], ents[0][3])
    sep = b"\x00" if b"\x00" in man else b"\n"
    paths = [p.decode("ascii") for p in man.split(sep) if p]
    by_hash = {e[0]: e for e in ents[1:]}
    files = {}
    for p in paths:
        e = by_hash[_md5(p)]
        files[p] = read(e[1], e[2], e[3])
    return files


def _selftest():
    import random
    samples = {
        "text2/eng.common": bytes(random.Random(1).randbytes(200000)),
        "fonts/seriffont-Regular.otf": b"OTTO" + bytes(range(256)) * 300,
        "a/tiny.bin": b"hello",
    }
    blob = build(samples)
    got = verify_read(blob)
    ok = got == samples
    print(f"build->read round-trip: {'OK' if ok else 'FAIL'}  ({len(blob):,} B, {len(samples)} files)")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="TLOU2R plain-PSARC override builder")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("out"); b.add_argument("kv", nargs="+")
    v = sub.add_parser("verify"); v.add_argument("archive")
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "selftest":
        sys.exit(_selftest())
    if a.cmd == "verify":
        f = verify_read(open(a.archive, "rb").read())
        for p, d in f.items():
            print(f"  {len(d):>12,}  {p}")
        return
    files = {}
    for kv in a.kv:
        path, local = kv.split("=", 1)
        files[path] = open(local, "rb").read()
    blob = build(files)
    with open(a.out, "wb") as fh:
        fh.write(blob)
    print(f"wrote {a.out}  ({len(blob):,} B)  {len(files)} files")


if __name__ == "__main__":
    main()
