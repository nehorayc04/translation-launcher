"""
WD2 .loc (Disrupt "SL" localization) decoder — faithful Python port of
ahmet-celik/watch-dogs-loc-tool Loc.cs (C#).

Format: header(12B) + 82 Tables -> SubTableMeta/SubTableIds (delta-ids, 64-id
blocks, pseudo-ids, lo/hi bit ranges) + tree_meta(12 thresholds, stored reversed)
+ Huffman tree (4B nodes; leaf<=0xFFFF=UTF-16 unit, else two 16b child idx) +
variable-bit-width Huffman bitstream (8/10/12/14/16/24 bits gated by tree_meta).

Stage 1 = DECODER only (validate + extract corpus). Encoder follows.

usage: python wd2_loc.py <main_xx.loc>   -> writes <loc>.txt (id=text)
"""
import struct, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MASK32 = 0xFFFFFFFF


class Buf:
    """seekable little-endian reader over bytes (mirrors Gibbed.IO usage)."""
    def __init__(self, data): self.d = data; self.p = 0
    def seek(self, pos): self.p = pos
    @property
    def pos(self): return self.p
    def s16(self): v = struct.unpack_from("<h", self.d, self.p)[0]; self.p += 2; return v
    def u16(self): v = struct.unpack_from("<H", self.d, self.p)[0]; self.p += 2; return v
    def u32(self): v = struct.unpack_from("<I", self.d, self.p)[0]; self.p += 4; return v
    def u32be(self): v = struct.unpack_from(">I", self.d, self.p)[0]; self.p += 4; return v
    def u8(self): v = self.d[self.p]; self.p += 1; return v


class Id:
    __slots__ = ("id", "lo", "hi", "increment", "is_pseudo", "str")
    def __init__(self, idv):
        self.id = idv; self.lo = 1; self.hi = 0
        self.increment = 0; self.is_pseudo = False; self.str = None

    def read(self, st, inp):
        """st = mutable [k, current_size_in_bits]. Mirrors Id.Read (ref k, ref csib)."""
        current_size = inp.u8()
        if current_size > 0xF0:
            self.increment = current_size - 240
            st[0] += (current_size - 240)          # k
            if st[0] > 64:
                raise RuntimeError(f"Extras! id={self.id} extra={st[0]-64}")
            self.is_pseudo = True
        else:
            if current_size == 0xF0:
                current_size = inp.u8()
                current_size = ((current_size << 8) + inp.u8()) + 5340
            elif current_size >= 0xDC:
                current_size = ((current_size << 8) + inp.u8()) - 56100
            if current_size != 0:
                current_size = 2 * current_size + 4
            self.increment = current_size
            self.lo = st[1]                          # current_size_in_bits
            st[1] += current_size
            self.hi = st[1]
            st[0] += 1                               # k


class SubTableMeta:
    __slots__ = ("max_id", "size", "delta_from_prev_id")
    def read(self, inp):
        first = inp.u16(); second = inp.u16()
        whole = (first << 16) + second
        self.delta_from_prev_id = second
        if whole >= 0x80000000:
            self.size = inp.u16()
            if ((whole >> 30) & 1) != 0:
                extra = inp.u16(); self.delta_from_prev_id += (extra << 16)
            self.max_id = first & 0x3FFF
        else:
            self.max_id = first >> 7
            self.size = (whole >> 12) & 0x7FF
            self.delta_from_prev_id &= 0xFFF


class SubTableIds:
    __slots__ = ("ids", "start", "id_begin")
    def __init__(self, start): self.start = start; self.ids = []; self.id_begin = 0

    def read(self, id_begin, meta, inp):
        """id_begin passed by value here; returns new id_begin (id_begin += id_count)."""
        self.id_begin = id_begin
        self.ids = []
        subtable_ids_begin = inp.pos
        id_count = meta.max_id + 1
        block_64ids_count = (id_count - 1) >> 6
        block_64ids_offsets = [inp.u16() for _ in range(block_64ids_count)]
        for j in range(0, id_count, 64):
            ids_in_block = []
            if j >= 64 and j % 64 == 0:
                off = block_64ids_offsets[(j >> 6) - 1]
                if off == 0:
                    self.ids.append(ids_in_block); continue
                inp.seek(subtable_ids_begin + off)
            st = [0, 0]  # [k, current_size_in_bits]
            limit = min(id_count - j, 64)
            while st[0] < limit:
                nid = Id(id_begin + j + st[0])
                nid.read(st, inp)
                ids_in_block.append(nid)
            delta = (inp.pos - self.start) << 3
            for nid in ids_in_block:
                nid.lo += delta; nid.hi += delta
            self.ids.append(ids_in_block)
        return id_begin + id_count


class Table:
    __slots__ = ("first_id", "offset", "length", "sub_metas", "sub_ids")
    def read(self, inp):
        self.first_id = inp.u32()
        offset_length = inp.u32()
        save = inp.pos
        self.offset = offset_length >> 4
        self.length = offset_length & 15
        inp.seek(self.offset)
        self.sub_metas = []
        for _ in range(self.length):
            m = SubTableMeta(); m.read(inp); self.sub_metas.append(m)
        self.sub_ids = []
        block_first_id = self.first_id
        block_position = inp.pos
        for i in range(self.length):
            inp.seek(block_position)
            block_first_id += self.sub_metas[i].delta_from_prev_id
            sti = SubTableIds(block_position)
            block_first_id = sti.read(block_first_id, self.sub_metas[i], inp)
            self.sub_ids.append(sti)
            block_position += self.sub_metas[i].size
        inp.seek(save)
        return block_position


class Loc:
    def read(self, inp):
        self.magic = inp.s16(); self.version = inp.s16()
        if self.magic != 0x4C53 or self.version != 1:
            raise RuntimeError("Not a valid loc file!")
        self.language = inp.s16()
        self.table_length = inp.u16()
        self.tree_offset = inp.u32()
        self.tables = []
        end_of_tables = -1
        for _ in range(self.table_length):
            t = Table(); end_of_tables = t.read(inp); self.tables.append(t)
        self.tree_meta_offset = (end_of_tables + (-end_of_tables & 3))
        tree_meta_length = (self.tree_offset - self.tree_meta_offset) >> 2
        self.tree_meta = [0] * tree_meta_length
        inp.seek(self.tree_meta_offset)
        for i in range(tree_meta_length):
            self.tree_meta[tree_meta_length - i - 1] = inp.u32()
        self.nodes_count = inp.u32()
        self.inp = inp

    def _dfs(self, out, tree_position):
        inp = self.inp; to = self.tree_offset
        stack = [tree_position & 0xFFFF]
        while stack:
            idx = stack.pop()
            inp.seek(to + 4 * idx)
            node = inp.u32()
            if node <= 0xFFFF:
                out.append(node)
            else:
                stack.append(node & 0xFFFF)
                stack.append((node >> 16) & 0xFFFF)

    def _find_tree_position(self, state):
        # state = dict with bit_length, byte_offset, bit_left, current_uint, current_uint_masked
        tm = self.tree_meta; inp = self.inp
        cum = state["cum"]
        was_24 = False
        if cum >= tm[6]:
            if cum >= tm[8]:
                if cum >= tm[10]:
                    raise RuntimeError("exit 42")
                was_24 = True
                state["bit_length"] -= 24
                tree_position = (tm[11] + cum) >> 8
                state["bit_left"] += 16
                inp.seek(state["byte_offset"])
                nb = inp.u8(); state["byte_offset"] += 1
                state["current_uint"] = ((state["current_uint"] << 24) + (nb << state["bit_left"])) & MASK32
                if state["bit_left"] >= 16:
                    state["bit_left"] -= 8
                    nb = inp.u8(); state["byte_offset"] += 1
                    state["current_uint"] = (state["current_uint"] + (nb << state["bit_left"])) & MASK32
            else:
                state["current_uint"] = (state["current_uint"] << 16) & MASK32
                state["bit_length"] -= 16
                tree_position = (tm[9] + cum) >> 16
                state["bit_left"] += 8
        else:
            if cum >= tm[2]:
                if cum >= tm[4]:
                    state["current_uint"] = (state["current_uint"] << 14) & MASK32
                    state["bit_length"] -= 14
                    tree_position = (tm[7] + cum) >> 18
                    state["bit_left"] += 6
                else:
                    state["current_uint"] = (state["current_uint"] << 12) & MASK32
                    state["bit_length"] -= 12
                    tree_position = (tm[5] + cum) >> 20
                    state["bit_left"] += 4
            else:
                if cum >= tm[0]:
                    state["current_uint"] = (state["current_uint"] << 10) & MASK32
                    state["bit_length"] -= 10
                    tree_position = (tm[3] + cum) >> 22
                    state["bit_left"] += 2
                else:
                    state["current_uint"] = (state["current_uint"] << 8) & MASK32
                    state["bit_length"] -= 8
                    tree_position = (tm[1] + cum) >> 24
        if not was_24:
            inp.seek(state["byte_offset"])
            nb = inp.u8(); state["byte_offset"] += 1
            state["current_uint"] = (state["current_uint"] + (nb << state["bit_left"])) & MASK32
        if state["bit_left"] >= 8:
            state["bit_left"] -= 8
            nb = inp.u8(); state["byte_offset"] += 1
            state["current_uint"] = (state["current_uint"] + (nb << state["bit_left"])) & MASK32
        return tree_position

    def decode_id(self, ids_start, idobj):
        bit_length = idobj.hi - idobj.lo
        if bit_length == 0:
            return ""
        out = []
        byte_offset = ids_start + (idobj.lo >> 3)
        bit_left = idobj.lo & 7
        self.inp.seek(byte_offset)
        current_uint = (self.inp.u32be() << bit_left) & MASK32
        byte_offset += 4
        state = {"bit_length": bit_length, "byte_offset": byte_offset,
                 "bit_left": bit_left, "current_uint": current_uint}
        while state["bit_length"] > 0:
            state["cum"] = state["current_uint"] & 0xFFFFFFE0
            tp = self._find_tree_position(state)
            self._dfs(out, tp)
        b = bytearray()
        for u in out:
            b += struct.pack("<H", u & 0xFFFF)
        return b.decode("utf-16-le", "replace")

    def export(self):
        """yield (id, text) for every non-pseudo Id."""
        for t in self.tables:
            for sti in t.sub_ids:
                for block in sti.ids:
                    for idobj in block:
                        if idobj.is_pseudo:
                            continue
                        idobj.str = self.decode_id(sti.start, idobj)
                        yield idobj.id, idobj.str


# ----------------------------------------------------------------------------
# ENCODER (repacker). Re-emits a valid .loc the game's decoder reads back.
# Strategy: reuse the parsed table/subtable/block/id structure (ids, grouping,
# pseudo-gaps, deltas, max_id) and substitute new strings. Uses a TRIVIAL entropy
# model: tree_meta forces the 16-bit path with base 0 -> tree_position == the top
# 16 bits == the code, and node[code] = char. So each UTF-16 unit = one 16-bit
# code, no Huffman tree construction needed.
# ----------------------------------------------------------------------------

def utf16_units(s):
    b = s.encode("utf-16-le")
    return list(struct.unpack("<%dH" % (len(b) // 2), b))


def encode_size(bit_length):
    """inverse of Id.Read: bit_length (=2s+4, or 0) -> size bytes."""
    if bit_length == 0:
        return bytes([0])
    assert bit_length >= 4 and (bit_length - 4) % 2 == 0, bit_length
    s = (bit_length - 4) // 2
    if s < 0xDC:
        return bytes([s])
    if s <= 5339:
        v = s + 56100                      # b0 in 0xDC..0xEF
        return bytes([(v >> 8) & 0xFF, v & 0xFF])
    v = s - 5340                           # 0xF0 escape
    assert v < 0x10000, "string too long for size encoding"
    return bytes([0xF0, (v >> 8) & 0xFF, v & 0xFF])


def encode_meta(max_id, size, delta):
    """SubTableMeta in the 'big' form (whole>=0x80000000)."""
    first = 0x8000 | (max_id & 0x3FFF)
    second = delta & 0xFFFF
    extra = delta >> 16
    if extra:
        first |= 0x4000
    out = struct.pack("<HHH", first, second, size)
    if extra:
        out += struct.pack("<H", extra & 0xFFFF)
    return out


def build_tree_meta(width):
    """tree_meta that forces a single fixed `width` (8/10/12/14/16) Huffman path
    with base 0, so tree_position == the top `width` bits == the code."""
    BIG = 0xFFFFFFFF
    tm = [0] * 12
    if width == 8:    # cum < tm[0] and < tm[2] and < tm[6]
        tm[0] = BIG; tm[2] = BIG; tm[6] = BIG; tm[1] = 0
    elif width == 10:  # tm[0] <= cum < tm[2] < tm[6]
        tm[0] = 0; tm[2] = BIG; tm[6] = BIG; tm[3] = 0
    elif width == 12:  # tm[2] <= cum < tm[4] < tm[6]
        tm[2] = 0; tm[4] = BIG; tm[6] = BIG; tm[5] = 0
    elif width == 14:  # tm[2]<=cum, tm[4]<=cum, cum<tm[6]
        tm[2] = 0; tm[4] = 0; tm[6] = BIG; tm[7] = 0
    elif width == 16:  # tm[6] <= cum < tm[8]
        tm[6] = 0; tm[8] = BIG; tm[9] = 0; tm[10] = BIG
    else:
        raise ValueError(width)
    return tm


class BitWriter:
    """MSB-first bit accumulator (matches the decoder's big-endian bit reader)."""
    __slots__ = ("acc", "nbits")
    def __init__(self): self.acc = 0; self.nbits = 0
    def write(self, value, n):
        self.acc = (self.acc << n) | (value & ((1 << n) - 1)); self.nbits += n
    def tobytes(self):
        pad = (-self.nbits) % 8
        total = self.nbits + pad
        return (self.acc << pad).to_bytes(total // 8, "big") if total else b""


SUBTABLE_LIMIT = 60000     # keep subtable bytes well under the u16 offset ceiling
MAX_SLOTS = 16000          # keep max_id under 0x3FFF


def _enc_block(block, width, code, new_strings):
    """one block -> [size bytes][bitstream] bytes."""
    sz = bytearray(); bw = BitWriter()
    for o in block:
        if o.is_pseudo:
            sz.append(0xF0 + o.increment)
        else:
            units = utf16_units(new_strings.get(o.id, ""))
            sz += encode_size(width * len(units))
            for u in units:
                bw.write(code[u], width)
    return bytes(sz) + bw.tobytes()


def _assemble_subtable(blocks, bb):
    """blocks + per-block bytes -> subtable bytes (offset array + block data).
    Block offsets are relative to the SUBTABLE START (the decoder captures
    subtable_ids_begin BEFORE reading the offset array), so they include the
    offset-array length."""
    oa_len = 2 * (len(bb) - 1) if bb else 0      # block_count = nblocks-1 entries
    offsets = []
    pos = oa_len + (len(bb[0]) if bb else 0)      # position right after block 0
    for b in range(1, len(bb)):
        if len(blocks[b]) == 0:
            offsets.append(0)
        else:
            offsets.append(pos)
            pos += len(bb[b])
    if any(o > 0xFFFF for o in offsets):
        raise OverflowError("subtable still >64KB after split")
    return b"".join(struct.pack("<H", o) for o in offsets) + b"".join(bb)


def encode(loc, new_strings):
    # 1. global char->code table (1-based; code 0 reserved = nodes_count slot)
    chars = set()
    for owner in loc.tables:
        for sti in owner.sub_ids:
            for block in sti.ids:
                for idobj in block:
                    if not idobj.is_pseudo:
                        chars.update(utf16_units(new_strings.get(idobj.id, "")))
    distinct = sorted(chars)
    code = {c: i + 1 for i, c in enumerate(distinct)}   # 1..K
    K = len(distinct)
    width = next(w for w in (8, 10, 12, 14, 16) if (1 << w) - 1 >= K)
    tree_meta = build_tree_meta(width)

    # 2. flatten to logical subtables (abs_start, id_count, blocks, per-block bytes),
    #    splitting any subtable that would exceed the u16 offset / max_id limits.
    logical = []  # list of (abs_start, id_count, blocks, bb)
    for t in loc.tables:
        for i, sti in enumerate(t.sub_ids):
            id_count = t.sub_metas[i].max_id + 1
            blocks = sti.ids
            bb = [_enc_block(b, width, code, new_strings) for b in blocks]
            nb = len(blocks)

            def bslots(bi, nb=nb, id_count=id_count):
                return 64 if bi < nb - 1 else id_count - 64 * (nb - 1)

            total = 2 * max(0, len(bb) - 1) + sum(len(x) for x in bb)
            if total <= SUBTABLE_LIMIT and id_count <= MAX_SLOTS:
                logical.append((sti.id_begin, id_count, blocks, bb))
                continue
            # greedy split on block boundaries
            start = 0; size = 0
            chunks = []
            for bi in range(nb):
                bsz = len(bb[bi])
                nblk = bi - start
                if bi > start and (size + bsz + 2 * nblk > SUBTABLE_LIMIT
                                   or (nblk + 1) * 64 > MAX_SLOTS):
                    chunks.append((start, bi - 1)); start = bi; size = 0
                size += bsz
            chunks.append((start, nb - 1))
            for a, b in chunks:
                cidc = sum(bslots(bi) for bi in range(a, b + 1))
                logical.append((sti.id_begin + 64 * a, cidc, blocks[a:b + 1], bb[a:b + 1]))

    # 3. group logical subtables into tables of <=15; recompute first_id + deltas
    groups = [logical[i:i + 15] for i in range(0, len(logical), 15)]
    table_first_ids = []
    table_blobs = []
    for grp in groups:
        first_id = grp[0][0]
        bfid = first_id
        metas = []; datas = []
        for abs_start, idc, blocks, bb in grp:
            delta = abs_start - bfid
            assert delta >= 0, (abs_start, bfid)
            sub = _assemble_subtable(blocks, bb)
            metas.append(encode_meta(idc - 1, len(sub), delta))
            datas.append(sub)
            bfid = abs_start + idc
        table_first_ids.append(first_id)
        table_blobs.append(b"".join(metas) + b"".join(datas))

    print(f"alphabet K={K} width={width}b  subtables {sum(len(t.sub_ids) for t in loc.tables)}"
          f"->{len(logical)}  tables {len(loc.tables)}->{len(groups)}")

    # 4. lay out: header(12) + table array(8*n) + table data + tree_meta + tree
    table_length = len(groups)
    out = bytearray()
    out += struct.pack("<hhhHI", 0x4C53, 1, loc.language, table_length, 0)  # tree_offset patched later
    data_base = 12 + 8 * table_length
    # table array
    pos = data_base
    table_array = bytearray()
    for ti, grp in enumerate(groups):
        offset_length = (pos << 4) | (len(grp) & 15)
        table_array += struct.pack("<II", table_first_ids[ti], offset_length)
        pos += len(table_blobs[ti])
    out += table_array
    for blob in table_blobs:
        out += blob
    end_of_tables = len(out)
    # tree_meta (aligned to 4, written REVERSED so decoder's reverse-read restores order)
    tm_off = (end_of_tables + 3) & ~3
    out += b"\x00" * (tm_off - end_of_tables)
    for v in reversed(tree_meta):
        out += struct.pack("<I", v & 0xFFFFFFFF)
    tree_offset = len(out)
    # tree: node[0] slot = nodes_count; node[code] = char  (code 1..K)
    nodes = [0] * (K + 1)
    nodes[0] = K + 1
    for c, cd in code.items():
        nodes[cd] = c
    for v in nodes:
        out += struct.pack("<I", v & 0xFFFFFFFF)
    out += b"\x00" * 8   # trailing pad (decoder over-reads u32be at string ends)
    struct.pack_into("<I", out, 8, tree_offset)
    return bytes(out)


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "encode":
        # encode <orig.loc> <strings.txt(id=text)> <out.loc>
        orig, txt, outp = sys.argv[2], sys.argv[3], sys.argv[4]
        loc = Loc(); loc.read(Buf(open(orig, "rb").read()))
        raw = open(txt, "rb").read()
        enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
        strings = {}
        for line in raw.decode(enc, "replace").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                if k.isdigit():
                    strings[int(k)] = v.replace("[CR]", "\r").replace("[LF]", "\n")
        blob = encode(loc, strings)
        open(outp, "wb").write(blob)
        print(f"encoded {len(strings)} strings -> {outp} ({len(blob)} bytes)")
        return
    path = sys.argv[1]
    data = open(path, "rb").read()
    loc = Loc(); loc.read(Buf(data))
    print(f"magic=SL ver={loc.version} lang={loc.language} tables={loc.table_length} "
          f"tree_offset={loc.tree_offset} tree_meta={loc.tree_meta} nodes_count={loc.nodes_count}")
    out = open(path + ".txt", "w", encoding="utf-8")
    n = 0
    for idv, txt in loc.export():
        out.write(f"{idv}={txt}".replace("\r", "[CR]").replace("\n", "[LF]") + "\n")
        n += 1
    out.close()
    print(f"decoded {n} strings -> {path}.txt")


if __name__ == "__main__":
    main()
