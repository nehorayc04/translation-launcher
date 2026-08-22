#!/usr/bin/env python3
"""
AC2 LocalizationPackage codec — DECODE side (pure Python).

resource (forge "FILEDATA"+name+DataFile) -> CompressedFileData blocks (LZO2A) ->
LocalizationPackage payload -> char-index string tables -> {id: text}.

Ported from the decompiled AnvilToolkit format (see ../FORMAT.md). Decompression
via ac2_lzo (bundled liblzo2). Usage:
    python ac2_loc.py <resource.bin>            # dump decoded strings
"""
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ac2_lzo

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CFD_MAGIC = bytes.fromhex("33aafb5799fa0410")   # 0x1004FA9957FBAA33, LE


def parse_cfd(d, pos):
    """Parse one CompressedFileData at pos -> (decompressed_bytes, end_pos)."""
    assert d[pos:pos+8] == CFD_MAGIC
    p = pos + 8
    _ver = struct.unpack_from("<h", d, p)[0]; p += 2
    algo = d[p]; p += 1
    _maxu = struct.unpack_from("<H", d, p)[0]; p += 2
    _maxc = struct.unpack_from("<H", d, p)[0]; p += 2
    nblocks = struct.unpack_from("<H", d, p)[0]; p += 2
    # per block: u16 UNCOMPRESSED size, u16 COMPRESSED size  (DataBlock.Read: num, num2)
    info = [struct.unpack_from("<HH", d, p + i*4) for i in range(nblocks)]
    p += nblocks * 4
    out = bytearray()
    for (usz, csz) in info:
        p += 4                                   # u32 block CRC32 (ignored on read)
        cdata = d[p:p+csz]; p += csz             # read COMPRESSED bytes
        out += cdata if usz == csz else ac2_lzo.decompress_block(algo, cdata, usz)
    return bytes(out), p


def extract_payload(resource: bytes) -> bytes:
    """Return the largest decompressed CFD = the LocalizationPackage container."""
    pos = resource.find(CFD_MAGIC)
    cfds = []
    while 0 <= pos < len(resource) - 8 and resource[pos:pos+8] == CFD_MAGIC:
        data, nxt = parse_cfd(resource, pos)
        cfds.append(data)
        pos = nxt if resource[nxt:nxt+8] == CFD_MAGIC else resource.find(CFD_MAGIC, nxt)
    if not cfds:
        raise RuntimeError("no CompressedFileData found")
    return max(cfds, key=len)


def _try_blob(blob):
    try:
        mi = struct.unpack_from(">H", blob, 0)[0]
        if not (1 <= mi <= 4096):
            return None
        nf = struct.unpack_from(">H", blob, 2)[0]
        if not (1 <= nf <= 30000) or 4 + nf*4 > len(blob):
            return None
        p = 4 + nf*4
        nt = struct.unpack_from(">H", blob, p)[0]; p += 2
        if not (1 <= nt <= 30000) or p + nt*12 > len(blob):
            return None
        tabs = [struct.unpack_from(">III", blob, p + i*12) for i in range(nt)]
        if any(ho >= len(blob) or eo >= len(blob) for _f, ho, eo in tabs):
            return None
        return mi, nf, tabs
    except Exception:
        return None


def decode_payload(payload: bytes):
    """Find + decode the char-index blob -> list of (id, text), plus metadata."""
    start, parsed = None, None
    for s in range(0, min(len(payload), 8000)):
        r = _try_blob(payload[s:])
        if r:
            # confirm it decodes to readable text before accepting
            try:
                strings = _decode_blob(payload[s:], r)
            except Exception:
                continue
            good = sum(1 for _i, t in strings
                       if t and any(c.isalpha() for c in t) and all(ord(c) < 0x600 for c in t))
            if good > 30:
                start, parsed = s, r
                return start, parsed, strings
    raise RuntimeError("LocalizationPackage blob not found in payload")


def _decode_blob(blob, parsed):
    max_index, nfrag, tables = parsed
    index_mask = max_index * 255
    frags = [struct.unpack_from(">HH", blob, 4 + i*4) for i in range(nfrag)]
    cache = {}

    def frag(i):
        if i in cache:
            return cache[i]
        rc, li = frags[i]
        s = "" if (li == 0 and rc == 0) else (chr(rc) if li == 0 else frag(li) + frag(rc))
        cache[i] = s
        return s

    out = []
    for (first_id, hdr_off, ent_off) in tables:
        ep = ent_off
        nent = struct.unpack_from(">H", blob, ep)[0]; ep += 2
        ids = [first_id]
        offs = [struct.unpack_from(">H", blob, ep)[0]]; ep += 2
        for _ in range(nent):
            ids.append(first_id + struct.unpack_from(">H", blob, ep)[0]); ep += 2
            offs.append(struct.unpack_from(">H", blob, ep)[0]); ep += 2
        pos = hdr_off; consumed = 0
        for k, end in enumerate(offs):
            sb = []
            while consumed < end:
                b = blob[pos]; pos += 1; consumed += 1
                if b < max_index:
                    sb.append(frag(b + 1))
                elif b == 0xFF:
                    num = struct.unpack_from(">h", blob, pos)[0]; pos += 2; consumed += 2
                    sb.append(frag(num + 1))
                else:
                    b2 = blob[pos]; pos += 1; consumed += 1
                    sb.append(frag(((b << 8) | b2) - index_mask + 1))
            out.append((ids[k], "".join(sb)))
    return out


# ----------------------------------------------------------------------------
# ENCODE side (mirrors AnvilToolkit LocalizationPackage.Write + ReadXml grouping)
def _group_tables(flat):
    """Group sorted (id, string) into tables: new table when id-FirstID >= 32767
    OR the table already holds 50 entries (matches ReadXml)."""
    flat = sorted(flat, key=lambda kv: kv[0])
    tables = []
    cur = []
    first = None
    for sid, s in flat:
        if not cur:
            first = sid
        if cur and (sid - first < 32767 and len(cur) < 50):
            cur.append((sid, s))
        elif not cur:
            cur.append((sid, s))
        else:
            tables.append((first, cur))
            first = sid
            cur = [(sid, s)]
    if cur:
        tables.append((first, cur))
    return tables


def encode_blob(flat, max_index=255):
    """Build the big-endian LocalizationPackage blob from (id, string) pairs."""
    tables = _group_tables(flat)
    # unique chars, sorted, "" at index 0
    chars = sorted({c for _i, s in flat for c in s})
    lst = [""] + chars
    idx = {c: i for i, c in enumerate(lst)}

    import io
    buf = io.BytesIO()
    w16 = lambda v: buf.write(struct.pack(">H", v & 0xFFFF))
    w32 = lambda v: buf.write(struct.pack(">I", v & 0xFFFFFFFF))

    w16(max_index)
    w16(len(lst))
    for c in lst:                              # fragments = leaves
        if c == "":
            w16(0); w16(0)
        else:
            w16(ord(c)); w16(0)
    w16(len(tables))
    hdr_pos = buf.tell()
    buf.write(b"\x00" * (12 * len(tables)))    # table headers (backfilled)

    meta = []   # (FirstEntryID, EntriesOffset, HeadersOffset)
    for first, entries in tables:
        ent_off = buf.tell()
        w16(len(entries) - 1)
        buf.write(b"\x00" * (len(entries) * 4 + 2))   # entry array (backfilled)
        hdr_off = buf.tell()
        offs = []
        for _sid, s in entries:
            n = 0
            for c in s:
                num = idx[c]
                if num < 255:
                    buf.write(bytes([num - 1])); n += 1
                else:
                    buf.write(b"\xff"); buf.write(struct.pack(">h", num - 1)); n += 3
            offs.append(n)
        # backfill entry array at ent_off+2: entry0 offset, then (id_delta,u16 cumOffset)
        end = buf.tell()
        buf.seek(ent_off + 2)
        cum = offs[0]
        w16(cum)
        for k in range(1, len(entries)):
            cum += offs[k]
            w16(entries[k][0] - first)
            w16(cum)
        buf.seek(end)
        meta.append((first, ent_off, hdr_off))

    # backfill table headers
    end = buf.tell()
    buf.seek(hdr_pos)
    for first, ent_off, hdr_off in meta:
        w32(first); w32(hdr_off); w32(ent_off)
    buf.seek(end)
    return buf.getvalue()


def _roundtrip(path):
    res = open(path, "rb").read()
    payload = extract_payload(res)
    start, parsed, strings = decode_payload(payload)
    blob2 = encode_blob(strings)
    # decode the re-encoded blob and compare
    p2 = _try_blob(blob2)
    strings2 = _decode_blob(blob2, p2)
    a = {i: s for i, s in strings}
    b = {i: s for i, s in strings2}
    same = a == b
    print(f"decoded {len(a)} strings; re-encoded blob {len(blob2):,} B; "
          f"re-decoded {len(b)} strings; identical={same}")
    if not same:
        diff = [(k, a.get(k), b.get(k)) for k in set(a) | set(b) if a.get(k) != b.get(k)]
        for k, x, y in diff[:8]:
            print(f"  [{k}] {x!r} != {y!r}")
    return same


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--roundtrip":
        sys.exit(0 if _roundtrip(sys.argv[2]) else 1)
    path = sys.argv[1]
    res = open(path, "rb").read()
    payload = extract_payload(res)
    print(f"resource {len(res):,} B -> payload {len(payload):,} B")
    start, parsed, strings = decode_payload(payload)
    mi, nf, tabs = parsed
    print(f"blob @0x{start:x}  MaxIndexSize={mi} fragments={nf} tables={len(tabs)}")
    print(f"decoded {len(strings)} strings")
    print("=== first 30 non-empty ===")
    n = 0
    for sid, s in strings:
        if s.strip():
            print(f"  [{sid}] {s!r}")
            n += 1
            if n >= 30:
                break
