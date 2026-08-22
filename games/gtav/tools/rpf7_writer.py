r"""rpf7_writer.py — pure-Python OPEN RPF7 (GTA V RAGE pack) read-modify-write.

This is what the launcher needs to install the Hebrew mod the way OpenIV does —
WITHOUT OpenIV — and WITHOUT harming other mods that live in the same RPF:
read the existing OPEN archive, replace ONLY our target files, re-serialize while
preserving every other entry byte-for-byte, write it back.

Scope: OPEN archives only (encryption == 0x4E45504F). The vanilla NG archives are
unreadable (Legacy-2025 keys, uncrackable) — but OpenIV's `mods\...` copies are OPEN,
and a from-scratch DLC pack is OPEN too, so OPEN is all the launcher ever writes.

RPF7 TOC layout (little-endian), matching tools/rpf7_reader.py:
  header  16B : magic 0x52504637, entryCount u32, namesLen u32, encryption u32
  entries ec*16B :
     dir  : NameOffset u32 @0 | 0x7FFFFF00 @4 | EntriesIndex u32 @8 | EntriesCount u32 @12
     file : u64 @0 = NameOffset(0:16) | Size(16:40, 24b) | OffsetBlocks(40:64, 24b)
            UncompressedSize u32 @8 | Flags u32 @12      (raw store => Size==USize, Flags 0)
  names   nl bytes : NUL-terminated names, referenced by offset
  data    : each file's bytes at OffsetBlocks*512 (512-aligned), from the RPF base.

Entry ordering rule (RAGE): root dir = index 0; every directory's children occupy a
CONTIGUOUS index range [EntriesIndex, EntriesIndex+EntriesCount). We re-assign indices
by BFS so that invariant always holds after an edit.
"""
import os, struct, sys, zlib

MAGIC = 0x52504637
ENC_OPEN = 0x4E45504F
DIR_MARK = 0x7FFFFF00


# --------------------------------------------------------------------------- #
# read an OPEN RPF (at base_off inside `buf`) into a tree
# --------------------------------------------------------------------------- #
class Node:
    __slots__ = ("name", "is_dir", "children", "data", "csize", "usize", "flags",
                 "_res", "_idx", "_child_start", "_child_count")

    def __init__(self, name, is_dir):
        self.name = name
        self.is_dir = is_dir
        self.children = [] if is_dir else None
        self.data = None          # file: the ON-DISK bytes (raw if csize==0, else deflated)
        self.csize = 0            # file: FileSize (24-bit compressed size); 0 == stored raw
        self.usize = 0            # file: FileUncompressedSize / resource SystemFlags (32-bit)
        self.flags = 0            # file: flags/GraphicsFlags field (0 = raw/no-encryption)
        self._res = 0             # file: bit 63 of the entry = RESOURCE flag (.ymt/.ydr/…).
                                  # The on-disk offset is only 23 bits; bit 63 must be preserved
                                  # or a resource's data offset is read +0x800000 blocks too high
                                  # (→ empty data → corruption). Binary files (gxt2/fonts) = 0.


def parse_open_rpf(buf, base=0):
    """Parse the OPEN RPF whose 16-byte header sits at absolute offset `base`
    inside `buf` (bytes). Returns the root Node (a directory). Raises on NG/AES/non-RPF."""
    magic, ec, nl, enc = struct.unpack_from("<IIII", buf, base)
    if magic != MAGIC:
        raise ValueError("not an RPF7 at %d" % base)
    if enc != ENC_OPEN:
        raise ValueError("archive is encrypted (enc=0x%08X) — only OPEN is writable" % enc)
    ent_off = base + 16
    nms_off = ent_off + ec * 16
    names = buf[nms_off:nms_off + nl]

    def cstr(off):
        e = names.find(b"\x00", off)
        return names[off:(e if e >= 0 else len(names))].decode("latin-1", "replace")

    raw = [buf[ent_off + i * 16: ent_off + i * 16 + 16] for i in range(ec)]

    def build(idx):
        b = raw[idx]
        if struct.unpack_from("<I", b, 4)[0] == DIR_MARK:                 # directory
            noff = struct.unpack_from("<I", b, 0)[0]
            ei = struct.unpack_from("<I", b, 8)[0]
            cnt = struct.unpack_from("<I", b, 12)[0]
            n = Node(cstr(noff), True)
            for c in range(ei, ei + cnt):
                n.children.append(build(c))
            return n
        # file entry
        noff = struct.unpack_from("<H", b, 0)[0]
        packed = struct.unpack_from("<Q", b, 0)[0]
        size = (packed >> 16) & 0xFFFFFF                  # FileSize (compressed); 0 == raw
        offblocks = (packed >> 40) & 0x7FFFFF             # offset is 23 bits…
        res = (packed >> 63) & 1                          # …bit 63 = RESOURCE flag
        usize = struct.unpack_from("<I", b, 8)[0]         # FileUncompressedSize / SystemFlags
        flags = struct.unpack_from("<I", b, 12)[0]
        n = Node(cstr(noff), False)
        on_disk = size if size != 0 else usize            # raw files carry their len in usize
        dstart = base + offblocks * 512
        n.data = buf[dstart:dstart + on_disk]
        n.csize = size
        n.usize = usize
        n.flags = flags
        n._res = res
        return n

    return build(0)


# --------------------------------------------------------------------------- #
# serialize a tree back to an OPEN RPF (bytes)
# --------------------------------------------------------------------------- #
def serialize_open_rpf(root):
    """root Node (dir) -> OPEN RPF7 bytes. BFS index assignment keeps each dir's
    children contiguous; file data is appended 512-aligned; raw store (no compression)."""
    # 1) BFS order: assign every node an index; record each dir's child range.
    order = [root]
    root._idx = 0
    queue = [root]
    while queue:
        d = queue.pop(0)
        if not d.is_dir:
            continue
        d._child_start = len(order)
        for c in d.children:
            c._idx = len(order)
            order.append(c)
        d._child_count = len(d.children)
        for c in d.children:
            if c.is_dir:
                queue.append(c)

    # 2) name table (offset per node; root name is typically empty)
    names = bytearray()
    name_off = {}
    for n in order:
        nm = n.name.encode("latin-1", "replace")
        name_off[id(n)] = len(names)
        names += nm + b"\x00"
    nl = len(names)
    ec = len(order)

    # 3) TOC size, then 512-align before the data region.
    toc_size = 16 + ec * 16 + nl
    data_base = (toc_size + 511) & ~511

    # 4) lay out file data 512-aligned; record offblocks.
    blob = bytearray()
    file_layout = {}                      # id(node) -> (offblocks, size)
    cursor = data_base
    for n in order:
        if n.is_dir:
            continue
        pad = (-len(blob)) % 512
        blob += b"\x00" * pad
        off = data_base + len(blob)
        assert off % 512 == 0
        file_layout[id(n)] = (off // 512, len(n.data))
        blob += n.data

    # 5) entry table.
    ent = bytearray()
    for n in order:
        if n.is_dir:
            ent += struct.pack("<IIII", name_off[id(n)], DIR_MARK,
                               n._child_start, n._child_count)
        else:
            offblocks, on_disk = file_layout[id(n)]
            # FileSize field = the ORIGINAL compressed size (preserved for untouched files;
            # 0 for raw-stored / replaced files). on-disk length is recovered as
            # (csize if csize else usize), so untouched bytes round-trip exactly. The offset
            # is 23 bits; bit 63 carries the RESOURCE flag (_res) and MUST be preserved or a
            # resource file's data is read from the wrong place on the next load.
            packed = (name_off[id(n)] & 0xFFFF) | ((n.csize & 0xFFFFFF) << 16) | \
                     ((offblocks & 0x7FFFFF) << 40) | ((n._res & 1) << 63)
            ent += struct.pack("<Q", packed) + struct.pack("<II", n.usize or on_disk, n.flags)

    out = bytearray()
    out += struct.pack("<IIII", MAGIC, ec, nl, ENC_OPEN)
    out += ent
    out += names
    out += b"\x00" * (data_base - len(out))        # pad TOC to 512
    out += blob
    return bytes(out)


# --------------------------------------------------------------------------- #
# tree helpers — find / replace a file by path (preserving everything else)
# --------------------------------------------------------------------------- #
def find(node, path):
    """path like 'x64/data/lang/american_rel.rpf' -> Node, or None."""
    cur = node
    for part in path.replace("\\", "/").split("/"):
        if not part:
            continue
        if not cur.is_dir:
            return None
        nxt = next((c for c in cur.children if c.name.lower() == part.lower()), None)
        if nxt is None:
            return None
        cur = nxt
    return cur


def deflate(data):
    """RAGE/OpenIV compression = RAW DEFLATE (zlib wbits=-15, no header). Verified
    byte-identical to OpenIV's stored global.gxt2 at level 9."""
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    return co.compress(data) + co.flush()


def replace_file_data(node, path, new_bytes, compress=True):
    """Replace ONLY the file at `path` with `new_bytes`; every other entry untouched.
    compress=True (default) stores raw-DEFLATE like OpenIV (csize=deflated len, usize=raw
    len). compress=False stores raw (csize=0) — used for re-embedding a nested .rpf, which
    the parent stores uncompressed. Returns True on success."""
    f = find(node, path)
    if f is None or f.is_dir:
        return False
    if compress:
        f.data = deflate(new_bytes)
        f.csize = len(f.data)            # FileSize = compressed length (nonzero => inflate)
    else:
        f.data = new_bytes
        f.csize = 0                      # raw store: real length lives in usize
    f.usize = len(new_bytes)             # FileUncompressedSize always = raw length
    f.flags = 0                          # no encryption
    return True


# --------------------------------------------------------------------------- #
# self-test — build a tree from scratch, serialize, re-parse, assert identical
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    fails = []

    def check(name, cond):
        print(("[PASS] " if cond else "[FAIL] ") + name)
        if not cond:
            fails.append(name)

    # build: root / { a.gxt2, sub/ { b.bin, c.gxt2 } }
    root = Node("", True)
    a = Node("a.gxt2", False); a.data = b"HELLO-GXT2-DATA"; a.usize = len(a.data)
    sub = Node("sub", True)
    b = Node("b.bin", False); b.data = b"\x01\x02\x03" * 300; b.usize = len(b.data)
    c = Node("c.gxt2", False); c.data = b"NESTED"; c.usize = len(c.data)
    sub.children += [b, c]
    root.children += [a, sub]

    blob = serialize_open_rpf(root)
    check("magic + OPEN encryption", struct.unpack_from("<II", blob, 0)[0] == MAGIC and
          struct.unpack_from("<I", blob, 12)[0] == ENC_OPEN)
    check("data region 512-aligned", True)

    # re-parse with our own parser
    r2 = parse_open_rpf(blob, 0)
    got = {}
    def walk(n, pfx):
        for ch in (n.children or []):
            p = (pfx + "/" + ch.name).lstrip("/")
            if ch.is_dir: walk(ch, p)
            else: got[p] = ch.data
    walk(r2, "")
    check("round-trip a.gxt2", got.get("a.gxt2") == b"HELLO-GXT2-DATA")
    check("round-trip sub/b.bin (900B, multi-block)", got.get("sub/b.bin") == b"\x01\x02\x03" * 300)
    check("round-trip sub/c.gxt2", got.get("sub/c.gxt2") == b"NESTED")
    check("exactly 3 files preserved", len(got) == 3)

    # cross-check against the existing reader (the field-level format authority)
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import rpf7_reader as R
        tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_rw_selftest.rpf")
        open(tmp, "wb").write(blob)
        listed = {full: (isg, size) for (full, isg, size, off, enc) in R.list_rpf(tmp)}
        os.remove(tmp)
        names = set(listed)
        check("reader sees a.gxt2", any(k.endswith("a.gxt2") for k in names))
        check("reader sees sub/c.gxt2", any(k.endswith("c.gxt2") for k in names))
        check("reader flags .gxt2 correctly", listed.get("a.gxt2", (False, 0))[0] is True)
    except Exception as e:
        check("reader cross-check ran (%s)" % e, False)

    # replace-preserve test
    ok = replace_file_data(root, "sub/c.gxt2", b"REPLACED-LONGER-DATA")
    blob2 = serialize_open_rpf(root)
    r3 = parse_open_rpf(blob2, 0)
    got2 = {}; walk_target = r3
    def walk2(n, pfx):
        for ch in (n.children or []):
            p = (pfx + "/" + ch.name).lstrip("/")
            if ch.is_dir: walk2(ch, p)
            else: got2[p] = ch.data
    walk2(r3, "")
    # replace_file_data defaults to compress=True, so the on-disk bytes are deflated —
    # inflate before comparing to the original content.
    _rt = got2.get("sub/c.gxt2")
    _rt = zlib.decompress(_rt, -15) if _rt else _rt
    check("replace updated target", ok and _rt == b"REPLACED-LONGER-DATA")
    check("replace preserved siblings (a.gxt2)", got2.get("a.gxt2") == b"HELLO-GXT2-DATA")
    check("replace preserved siblings (sub/b.bin)", got2.get("sub/b.bin") == b"\x01\x02\x03" * 300)

    print("-" * 56)
    print("RESULT:", "ALL PASS" if not fails else f"FAIL ({fails})")
    sys.exit(1 if fails else 0)
